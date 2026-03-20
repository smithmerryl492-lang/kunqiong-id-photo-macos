"""证件照模块 - 自动抠图+换背景色+标准尺寸（符合中国证件照标准）"""
import os
import cv2
import numpy as np
from modules.base_module import BaseModule
from utils.image_utils import save_image, create_temp_file, cv2_imread
from utils.config import _get_resource_path, get_hivision_modnet_onnx_path
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSlider, QPushButton
from PyQt6.QtCore import Qt, QTimer
from ui.custom_widgets import StyledComboBox

# 模块级缓存，避免重复导入
_rembg_module = None


def translate_color_dialog_to_chinese(dialog):
    """
    将颜色选择器的所有英文文本翻译为中文
    """
    from PyQt6.QtWidgets import QPushButton, QLabel
    
    # 使用QTimer延迟执行，确保对话框已完全初始化
    def do_translate():
        # 翻译所有按钮文本
        for button in dialog.findChildren(QPushButton):
            text = button.text()
            if text:
                # 去除快捷键标记（&符号）
                text_clean = text.replace('&', '').strip().lower()
                
                # 翻译常见按钮文本
                if text_clean == 'ok':
                    button.setText('确定')
                elif text_clean == 'cancel':
                    button.setText('取消')
                elif 'pick screen color' in text_clean:
                    button.setText('屏幕取色')
                elif 'add to custom colors' in text_clean:
                    button.setText('添加到自定义颜色')
        
        # 翻译所有标签文本
        for label in dialog.findChildren(QLabel):
            text = label.text()
            if text:
                text_clean = text.replace('&', '').replace(':', '').strip().lower()
                
                # 翻译颜色参数标签
                translations = {
                    'hue': '色调',
                    'sat': '饱和度',
                    'val': '明度',
                    'red': '红色',
                    'green': '绿色',
                    'blue': '蓝色',
                    'alpha': '透明度',
                    'html': 'HTML',
                    'basic colors': '基本颜色',
                    'custom colors': '自定义颜色',
                    'pick screen color': '屏幕取色'
                }
                
                if text_clean in translations:
                    # 保留原有的冒号
                    if ':' in text:
                        label.setText(translations[text_clean] + ':')
                    else:
                        label.setText(translations[text_clean])
    
    # 延迟50ms执行翻译，确保对话框完全加载
    QTimer.singleShot(50, do_translate)


class IDPhotoModule(BaseModule):
    """证件照模块 - 符合中国证件照标准"""
    
    # 裁剪算法参数
    # 人脸面积与全图面积的期望比值
    HEAD_MEASURE_RATIO = 0.2
    
    # 人脸中心处在全图高度的比例期望值
    HEAD_HEIGHT_RATIO = 0.45
    
    # 头距离顶部的比例（max, min）
    HEAD_TOP_RANGE = (0.12, 0.1)
    
    # 人脸检测框扩展比例（人脸框从眉毛开始，需要向上扩展到头顶）
    FOREHEAD_EXTENSION = 0.30
    
    def __init__(self):
        super().__init__(
            name="证件照",
            description="自动抠图、更换背景颜色、生成标准证件照（符合中国标准）",
            icon="🪪"
        )
        
        # 初始化美颜参数（必须在构造函数中初始化）
        self.beauty_params = {
            'enabled': False,      # 是否启用美颜
            'whitening': 0,
            'brightness': 0,
            'contrast': 0,
            'saturation': 0,
            'sharpen': 0
        }
        
        # 初始化模式参数
        self.mode = 'size_list'  # 'size_list', 'only_change_bg', 'custom_px', 'custom_mm'
        self.custom_size = (413, 295)  # 默认一寸 (高, 宽)
        
        # 模型选择配置
        self.matting_model = 'hivision_modnet'
        self.face_detect_model = 'mtcnn'  # 'mtcnn', 'retinaface'
        
        # 初始化高级参数
        self.advanced_params = {
            'head_measure_ratio': 0.2,    # 人脸面积占比 0.15-0.25
            'top_distance_max': 0.12,     # 头顶距离上边界 0.10-0.15
        }
        self.watermark_params = {
            'enabled': False,          # 是否启用水印
            'type': 'text',            # 水印类型：'text' 或 'image'
            # 文字水印参数
            'text': '鲲穹AI',          # 水印文字
            'font_family': '微软雅黑',  # 字体
            'size': 20,                # 字体大小 10-100
            'opacity': 0.15,           # 透明度 0-1
            'angle': 30,               # 角度 0-360
            'color': '#8B8B1B',        # 颜色
            'space': 25,               # 间距 10-200
            'position': 'tiled',       # 位置：tiled/top_left/top_right/bottom_left/bottom_right
            # 图片水印参数
            'image_path': None,        # 水印图片路径
            'image_opacity': 0.3,      # 图片透明度
            'image_scale': 0.1,        # 图片缩放比例
            'image_remove_bg': False,  # 是否去除背景色（使用透明背景）
        }
        
        # 初始化KB大小和DPI参数
        self.output_params = {
            'kb_enabled': False,       # 是否启用KB大小控制
            'target_kb': 50,           # 目标KB大小 (30-200)
            'kb_mode': 'max',          # 模式: 'exact'(精确), 'max'(不大于)
            'dpi_enabled': False,      # 是否启用DPI设置
            'dpi': 300,                # DPI值 (300/600)
        }
        
        # 插件功能参数
        self.plugin_params = {
            'face_alignment': False,        # 人脸旋转对齐
            'horizontal_flip': False,       # 水平翻转
            'layout_crop_line': True,       # 排版照裁剪线（默认开启）
            'jpeg_format': False,           # JPEG格式输出
        }
        
        # 输出照片类型参数
        self.output_types = {
            'standard_photo': True,         # 标准照（默认）
            'hd_photo': False,              # 高清照（HD Photo）
            'matting_standard': False,      # 透明标准照
            'matting_hd': False,            # 透明高清照
            'layout_photo': False,          # 排版照
        }
        
        # 打印排版参数
        self.print_params = {
            'enabled': False,               # 是否启用打印排版
            'paper_size': '六寸',          # 相纸选择：六寸/五寸/A4/3R/4R
        }
        # 相纸尺寸（像素）- 注意：这里只是UI显示用的，实际排版使用create_print_layout中的定义
        self.paper_sizes = {
            '六寸': (1795, 2398),       # 6寸 = 6R = 152×203mm (竖向)
            '五寸': (1500, 2100),       # 5寸 = 5R = 127×178mm
            'A4': (2480, 3508),         # A4 = 210×297mm
            '3R': (1050, 1500),         # 3R = 3.5×5 inch = 89×127mm
            '4R': (1205, 1795),         # 4R = 4×6 inch = 102×152mm (横向，与六寸不同)
        }
        # 背景颜色选项 (BGR格式，OpenCV使用BGR)
        # 常用证件照背景色标准
        self.bg_colors = {
            '白色': (255, 255, 255),           # 护照、身份证、教师资格证等
            '蓝色': (219, 142, 67),             # 标准证件照蓝色 RGB(67,142,219)
            '浅蓝色': (235, 180, 120),          # 淡蓝色 RGB(120,180,235)
            '深蓝色': (180, 100, 50),           # 深蓝色 RGB(50,100,180)
            '红色': (67, 67, 219),               # 标准证件照红色 RGB(219,67,67)
            '深红色': (60, 60, 180),             # 深红色 RGB(180,60,60)
            '灰色': (200, 200, 200),             # 浅灰色
        }
        
        # 自定义颜色缓存
        self.custom_color = (255, 255, 255)  # 默认白色
        
        # 渲染模式
        self.render_mode = 'pure_color'  # 'pure_color', 'updown_gradient', 'center_gradient'
        # 标准尺寸选项 (宽x高，单位像素，300dpi 除非特别标注)
        # 格式说明：一寸 25×35mm = 295×413px @300dpi
        # 
        # 智能算法设计
        # 
        # 本模块使用智能算法自动计算最佳 head_measure_ratio 和 top_distance：
        # 1. 通过 MTCNN 检测人脸和关键点
        # 2. 分析原图拍摄类型（特写/半身/全身）
        # 3. 计算头部占比和身体比例
        # 4. 根据证件照类型和原图特征，自动调整参数
        # 5. 应用算法生成证件照
        # 
        # 优势：
        # - 自适应：适应不同人、不同拍摄距离
        # - 智能化：无需用户手动调整
        # - 精准：基于标准和实际照片特征
        # 
        self.sizes = {
            # 格式：名称: (宽, 高)
            # 注意：不再预设 crop_params，由智能算法自动计算
            # 顺序：最常用的放在前面
            
            # ===== 最常用 =====
            '一寸 (25×35mm)': (295, 413),
            '二寸 (35×49mm)': (413, 579),
            '身份证 (26×32mm)': (358, 441),      # @350dpi, 露出锁骨
            '不裁剪': (None, None),
            
            # ===== 常用尺寸 =====
            '小一寸 (22×32mm)': (260, 378),
            '小二寸 (35×45mm)': (413, 531),
            '大一寸 (33×48mm)': (390, 567),
            '大二寸 (35×53mm)': (413, 626),
            
            # ===== 身份证件 =====
            '社保卡 (26×32mm)': (358, 441),      # 同身份证
            '驾驶证 (22×32mm)': (260, 378),
            '电子驾驶证 (22×32mm)': (260, 378),
            
            # ===== 护照/签证（常用） =====
            '中国护照 (33×48mm)': (390, 567),     # 头長28-33mm，头顶距离3-5mm
            '美国签证 (51×51mm)': (600, 600),     # 2x2英寸，头占比50%-70%
            '日本签证 (35×45mm)': (413, 531),     # 头占比70%
            '韩国签证 (35×45mm)': (413, 531),     # 头镲32-36mm
            
            # ===== 考试证件（常用） =====
            '教师资格证 (25×35mm)': (295, 413),   # 一寸
            '国家公务员考试 (25×35mm)': (295, 413),  # 一寸
            '研究生考试 (33×48mm)': (390, 567),  # 大一寸
            '初级会计考试 (25×35mm)': (295, 413),
            '英语四六级考试 (144×192px)': (144, 192),  # 特殊尺寸
            '计算机等级考试 (144×192px)': (144, 192),  # 头占比70%
            
            # ===== 其他尺寸 =====
            '五寸 (89×127mm)': (1050, 1499),
        }
    
    def get_system_requirements(self) -> dict:
        """获取系统配置要求"""
        return {
            'min_cpu': '4核心',
            'min_ram': '8GB',
            'rec_cpu': '8核心',
            'rec_ram': '12GB'
        }
    
    def load_model(self):
        """加载抠图模型目录（打包时用 _MEIPASS 下固定路径）"""
        if self.model is None:
            try:
                import shutil
                import tempfile
                # 打包环境：直接用 hivision_modnet.onnx 所在目录
                onnx_file = get_hivision_modnet_onnx_path()
                model_dir = os.path.dirname(onnx_file)
                try:
                    model_dir.encode('ascii')
                    self.safe_model_dir = model_dir
                except UnicodeEncodeError:
                    self.safe_model_dir = os.path.join(tempfile.gettempdir(), "u2net_models")
                    os.makedirs(self.safe_model_dir, exist_ok=True)
                    if os.path.isfile(onnx_file):
                        shutil.copy2(onnx_file, os.path.join(self.safe_model_dir, "hivision_modnet.onnx"))
                os.environ["U2NET_HOME"] = self.safe_model_dir
                self.model = None
                self.model_loaded = True
            except ImportError:
                raise ImportError("请安装 rembg 库: pip install rembg")
    
    def process(self, image_path: str, bg_color: str = '白色', size: str = '不裁剪', 
                whitening: int = 0, brightness: int = 0, contrast: int = 0, 
                saturation: int = 0, sharpen: int = 0, 
                mode: str = None, render_mode: str = None, 
                custom_color: tuple = None, advanced_params: dict = None, 
                output_params: dict = None, plugin_params: dict = None, 
                output_types: dict = None, print_params: dict = None, **kwargs) -> str:
        """
        处理证件照
        
        Args:
            image_path: 输入图片路径
            bg_color: 背景颜色名称
            size: 输出尺寸名称
            whitening: 美白强度 0-15
            brightness: 亮度调整 -5~+25
            contrast: 对比度调整 -10~+50
            saturation: 饱和度调整 -10~+50
            sharpen: 锐化强度 0-5
            mode: 尺寸模式 - '尺寸列表', '只换底', '自定义(px)', '自定义(mm)'
            render_mode: 渲染模式 - '纯色', '上下渐变（白色）', '中心渐变（白色）'
            custom_color: 自定义背景色 (B, G, R)
            advanced_params: 高级参数（head_measure_ratio, top_distance_max）
            output_params: 输出设置（KB大小和DPI）
            plugin_params: 插件功能参数
            output_types: 输出照片类型
            print_params: 打印排版参数
            **kwargs: 其他参数
            
        Returns:
            处理后的图片路径
        """
        self.ensure_model_loaded()
        
        # 应用传入的参数
        if mode:
            # 将中文模式文本转换为英文标识符
            mode_map = {
                "尺寸列表": 'size_list',
                "只换底": 'only_change_bg',
                "自定义(px)": 'custom_px',
                "自定义(mm)": 'custom_mm',
            }
            self.mode = mode_map.get(mode, mode)  # 如果已经是英文标识符，则直接使用
        if render_mode:
            self.render_mode = render_mode
        if custom_color:
            self.custom_color = custom_color
        if advanced_params:
            self.advanced_params.update(advanced_params)
        if output_params:
            self.output_params.update(output_params)
        if plugin_params:
            self.plugin_params.update(plugin_params)
        if output_types:
            self.output_types.update(output_types)
        if print_params:
            self.print_params.update(print_params)
        
        # 设置模型路径
        os.environ["U2NET_HOME"] = self.safe_model_dir
        
        # 抠图模型：仅 hivision_modnet（打包时用固定路径）
        model_file = get_hivision_modnet_onnx_path()
        if not os.path.isfile(model_file):
            fallback = os.path.join(self.safe_model_dir, "hivision_modnet.onnx")
            if os.path.isfile(fallback):
                model_file = fallback
            else:
                raise FileNotFoundError(
                    "未找到抠图模型 hivision_modnet.onnx！\n"
                    f"路径: {model_file}\n"
                    "请确认 models/u2net/ 已打包或运行: python download_hivision_models.py"
                )
        print("[证件照] 使用模型: hivision_modnet")
        
        # 0. 先读取原图
        original_img = cv2_imread(image_path)
        if original_img is None:
            raise RuntimeError("无法读取图片")
        
        orig_h, orig_w = original_img.shape[:2]
        
        # 0.1 在原图上检测人脸（原图可能包含更多内容）
        # 使用用户指定的人脸检测器
        face_info_original = self._detect_face(original_img, method=self.face_detect_model)
        
        # 1. 使用抠图模型（hivision_modnet）
        from utils.modnet_matting import MODNetMatting
        modnet = MODNetMatting(model_file)
        img_rgba = modnet.process(original_img)
        
        if img_rgba is None:
            raise RuntimeError("抠图失败")
        
        # 1.5 分析人体边界（抠图结果）
        person_bounds = self._analyze_person_bounds(img_rgba)
        
        # 使用原图的人脸检测结果（更准确，因为原图可能更完整）
        if person_bounds and face_info_original:
            person_bounds['face_info'] = face_info_original
        
        # 1.6 平滑边缘（羽化处理）
        img_rgba = self._smooth_edges(img_rgba)
        
        # 1.7 应用美颜效果（官方顺序：先美颜，再裁剪）
        # 注意：只有在启用美颜且参数不全为0时才应用
        if self.beauty_params.get('enabled', False):
            whitening = self.beauty_params.get('whitening', 0)
            brightness = self.beauty_params.get('brightness', 0)
            contrast = self.beauty_params.get('contrast', 0)
            saturation = self.beauty_params.get('saturation', 0)
            sharpen = self.beauty_params.get('sharpen', 0)
            
            # 检查是否有非0参数
            if any([whitening, brightness, contrast, saturation, sharpen]):
                print(f"\n[==========  应用美颜效果  ==========]")
                print(f"美白: {whitening}, 亮度: {brightness}, 对比度: {contrast}")
                print(f"饱和度: {saturation}, 锐化: {sharpen}")
                print(f"[====================================]\n")
                
                img_rgba = self._apply_beauty_effects(
                    img_rgba,
                    whitening=whitening,
                    brightness=brightness,
                    contrast=contrast,
                    saturation=saturation,
                    sharpen=sharpen
                )
            else:
                print(f"\n[美颜] 已启用但所有参数为0，跳过美颜处理\n")
        else:
            print(f"\n[美颜] 未启用，跳过美颜处理\n")
        
        # 1.8 应用插件功能（官方）
        # 人脸旋转对齐
        if self.plugin_params.get('face_alignment', False) and face_info_original:
            img_rgba = self._apply_face_alignment(img_rgba, face_info_original)
        
        # 水平翻转
        if self.plugin_params.get('horizontal_flip', False):
            img_rgba = cv2.flip(img_rgba, 1)  # 1表示水平翻转
        
        # 2. 裁剪到标准尺寸（使用智能算法）
        # 注意：只换底模式不进行裁剪
        
        # 确定目标尺寸
        target_size = None
        if self.mode == 'only_change_bg':
            # 只换底模式：不裁剪
            print(f"\n[==========  只换底模式  ==========]")
            print(f"保持原图尺寸，不进行裁剪")
            print(f"原图尺寸: {orig_w}x{orig_h}px")
            print(f"[==================================]\n")
        elif self.mode in ['custom_px', 'custom_mm']:
            # 自定义尺寸模式
            target_h, target_w = self.custom_size
            target_size = (target_w, target_h)
            print(f"\n[==========  自定义尺寸模式  ==========]")
            print(f"自定义尺寸: {target_w}x{target_h}{'px' if self.mode == 'custom_px' else 'mm'}")
            print(f"[====================================]\n")
        else:
            # 尺寸列表模式
            size_config = self.sizes.get(size)
            if size_config and size_config[0] is not None:
                target_w, target_h = size_config
                target_size = (target_w, target_h)
        
        # 根据输出类型调整分辨率：高清照/透明高清照为 2 倍
        if target_size and (self.output_types.get('hd_photo') or self.output_types.get('matting_hd')):
            target_w, target_h = target_size
            target_w, target_h = target_w * 2, target_h * 2
            target_size = (target_w, target_h)
        
        # 如果有目标尺寸，执行裁剪
        if target_size:
            target_w, target_h = target_size
                    
            # ===== 智能算法：自动计算最佳参数 =====
            crop_params = None
            face_info = person_bounds.get('face_info') if person_bounds else None
                    
            if face_info:
                # Step 1: 分析原图特征（拍摄类型）
                characteristics = self._analyze_photo_characteristics(img_rgba, face_info, person_bounds)
                        
                # Step 2: 根据证件照类型调整参数
                head_measure_ratio, top_distance_max, top_distance_min = self._adjust_for_id_type(
                    characteristics, size
                )
                        
                # 构建裁剪参数
                crop_params = (
                    head_measure_ratio,
                    0.45,  # head_height_ratio 保持默认
                    (top_distance_max, top_distance_min)
                )
                        
                # 打印日志（方便调试）
                print(f"\n[==========  智能证件照参数  ==========]")
                if self.mode in ['custom_px', 'custom_mm']:
                    print(f"证件照类型: 自定义尺寸")
                else:
                    print(f"证件照类型: {size}")
                print(f"目标尺寸: {target_w}x{target_h}px")
                print(f"\n原图分析:")
                print(f"  - 拍摄类型: {characteristics['shot_type']}")
                if characteristics['shot_type'] == 'close_up':
                    print(f"    (特写照：只有头和一点肩膀)")
                elif characteristics['shot_type'] == 'half_body':
                    print(f"    (半身照：到腰部或更多)")
                else:
                    print(f"    (全身照)")
                print(f"  - 头部占比: {characteristics['head_ratio']:.1%}")
                print(f"  - 头部高度: {characteristics['head_height']}px")
                print(f"  - 总高度: {characteristics['total_height']}px")
                print(f"\n智能调整:")
                print(f"  - 基础推荐 head_measure_ratio: {characteristics['recommended_measure']:.3f}")
                print(f"  - 基础推荐 top_distance: {characteristics['recommended_top_distance']:.3f}")
                print(f"  - 调整后 head_measure_ratio: {head_measure_ratio:.3f}")
                print(f"  - 调整后 top_distance: {top_distance_max:.3f} ~ {top_distance_min:.3f}")
                print(f"[========================================]\n")
            else:
                print(f"\n[==========  警告  ==========]")
                print(f"未检测到人脸，使用默认参数")
                print(f"[===========================]\n")
                    
            # 使用智能裁剪方法
            img_rgba = self._smart_crop_for_id_photo(img_rgba, target_size, person_bounds, (orig_w, orig_h), crop_params)
        
        # 3. 获取目标背景色（用于颜色去污）
        bg_name = bg_color if isinstance(bg_color, str) else '白色'
        target_bg = self.bg_colors.get(bg_name, (255, 255, 255))
        
        # 处理渐变色情况（使用起始色）
        if isinstance(target_bg, str):
            target_bg = (255, 255, 255)  # 默认白色
        
        # 4. 颜色去污（使用目标背景色，减少边缘溢色）
        img_rgba = self._color_decontamination(img_rgba, target_bg)
        
        # 5. 保存RGBA结果（带alpha通道，供UI层动态换背景色）
        # 注意：水印将在UI层应用背景色之后添加，确保水印在最终图像上
        output_path = create_temp_file(suffix='.png', prefix='id_photo_')
        # 使用 imencode 支持中文路径
        success, encoded = cv2.imencode('.png', img_rgba, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        if success:
            with open(output_path, 'wb') as f:
                f.write(encoded.tobytes())
            return output_path
        else:
            raise RuntimeError("保存处理结果失败")
    
    def _apply_background_color(self, img_rgba: np.ndarray, bg_color: tuple) -> np.ndarray:
        """
        将RGBA图像的透明区域填充为指定背景色
        
        Args:
            img_rgba: RGBA格式图像
            bg_color: BGR格式背景色 (B, G, R)
        
        Returns:
            BGR格式图像（无透明通道）
        """
        if img_rgba.shape[2] != 4:
            return img_rgba
        
        # 分离通道
        b, g, r, a = cv2.split(img_rgba)
        
        # 创建背景
        h, w = img_rgba.shape[:2]
        bg = np.zeros((h, w, 3), dtype=np.uint8)
        bg[:, :] = bg_color  # BGR格式
        
        # Alpha混合
        alpha = a.astype(np.float32) / 255.0
        alpha_3ch = np.stack([alpha, alpha, alpha], axis=2)
        
        # 前景（BGR）
        fg = cv2.merge([b, g, r])
        
        # 混合：result = fg * alpha + bg * (1 - alpha)
        result = (fg.astype(np.float32) * alpha_3ch + 
                  bg.astype(np.float32) * (1 - alpha_3ch))
        
        return result.astype(np.uint8)
    
    def _smooth_edges(self, img_rgba: np.ndarray, feather: int = 2) -> np.ndarray:
        """轻微平滑边缘，消除抠图锯齿，保持清晰度"""
        if img_rgba.shape[2] != 4:
            return img_rgba
        
        # 获取alpha通道
        alpha = img_rgba[:, :, 3].copy()
        
        # 使用较小的模糊核，只做轻微平滑
        alpha_blurred = cv2.GaussianBlur(alpha, (feather * 2 + 1, feather * 2 + 1), 0)
        
        # 只在边缘区域应用模糊（保持内部不变）
        # 使用较小的kernel减少影响范围
        kernel = np.ones((3, 3), np.uint8)
        alpha_dilated = cv2.dilate(alpha, kernel, iterations=1)
        alpha_eroded = cv2.erode(alpha, kernel, iterations=1)
        edge_mask = ((alpha_dilated > 0) & (alpha_eroded < 255)).astype(np.float32)
        
        # 在边缘区域混合原始alpha和模糊后的alpha
        alpha_result = alpha * (1 - edge_mask) + alpha_blurred * edge_mask
        img_rgba[:, :, 3] = alpha_result.astype(np.uint8)
        
        return img_rgba
    
    def _color_decontamination(self, img_rgba: np.ndarray, target_bg_color: tuple) -> np.ndarray:
        """
        颜色去污 - 消除边缘的原背景色残留
        将半透明边缘区域的颜色向目标背景色偏移，减少颜色溢出
        使用温和的处理保持图片质量
        """
        if img_rgba.shape[2] != 4:
            return img_rgba
        
        alpha = img_rgba[:, :, 3].astype(np.float32) / 255.0
        rgb = img_rgba[:, :, :3].astype(np.float32)
        
        # 只处理半透明边缘区域（alpha在0.1-0.9之间）
        edge_mask = ((alpha > 0.1) & (alpha < 0.9)).astype(np.float32)
        
        if edge_mask.sum() == 0:
            return img_rgba
        
        # 计算边缘强度（越接近0.5的alpha，去污越强）
        decontam_strength = np.exp(-((alpha - 0.5) ** 2) / (2 * 0.2 ** 2))
        decontam_strength = decontam_strength * edge_mask
        
        # 目标背景色
        target_color = np.array(target_bg_color, dtype=np.float32)
        
        # 温和的混合比例，减少对图片质量的影响
        blend_factor = 0.2
        for c in range(3):
            color_shift = (target_color[c] - rgb[:, :, c]) * decontam_strength * blend_factor
            rgb[:, :, c] = np.clip(rgb[:, :, c] + color_shift, 0, 255)
        
        img_rgba[:, :, :3] = rgb.astype(np.uint8)
        return img_rgba
    
    def _apply_face_alignment(self, img_rgba: np.ndarray, face_info: dict) -> np.ndarray:
        """
        人脸旋转对齐（官方插件功能）
        根据人脸关键点计算旋转角度，使人脸水平对齐
        """
        try:
            if 'landmarks' not in face_info or face_info['landmarks'] is None:
                print("[人脸对齐] 未找到landmarks信息")
                return img_rgba
            
            landmarks = face_info['landmarks']
            
            # 调试信息
            print(f"[人脸对齐] landmarks类型: {type(landmarks)}")
            print(f"[人脸对齐] landmarks内容: {landmarks}")
            
            # 确保landmarks不是None或标量
            if landmarks is None:
                print("[人脸对齐] landmarks是None")
                return img_rgba
            
            if isinstance(landmarks, (int, float, np.integer, np.floating)):
                print(f"[人脸对齐] landmarks是标量: {landmarks}")
                return img_rgba
            
            if not isinstance(landmarks, (list, np.ndarray)):
                print(f"[人脸对齐] landmarks类型错误: {type(landmarks)}")
                return img_rgba
            
            # 转换为numpy数组
            if isinstance(landmarks, list):
                if len(landmarks) == 0:
                    print("[人脸对齐] landmarks是空列表")
                    return img_rgba
                landmarks = np.array(landmarks)
            
            # 检查是否为0维数组
            if landmarks.ndim == 0:
                print(f"[人脸对齐] landmarks是0维数组: {landmarks}")
                return img_rgba
            
            print(f"[人脸对齐] landmarks形状: {landmarks.shape}, ndim: {landmarks.ndim}")
            
            # 处理一维数组（MTCNN格式：[x0,x1,x2,x3,x4,y0,y1,y2,y3,y4]）
            if landmarks.ndim == 1:
                if len(landmarks) == 10:
                    # MTCNN格式：前5个x坐标，后5个y坐标
                    print("[人脸对齐] 检测到MTCNN格式，转换为5x2")
                    left_eye = np.array([landmarks[0], landmarks[5]])
                    right_eye = np.array([landmarks[1], landmarks[6]])
                elif len(landmarks) >= 4:
                    # 可能是其他格式，尝试使用前4个值作为两眼坐标
                    print("[人脸对齐] 使用前4个值作为两眼坐标")
                    left_eye = np.array([landmarks[0], landmarks[1]])
                    right_eye = np.array([landmarks[2], landmarks[3]])
                else:
                    print(f"[人脸对齐] landmarks一维数组长度不对: {len(landmarks)}")
                    return img_rgba
            
            # 处理二维数组（RetinaFace格式：[[x0,y0],[x1,y1],...]）
            elif landmarks.ndim == 2:
                if landmarks.shape[0] < 2:
                    print(f"[人脸对齐] landmarks点数不足: {landmarks.shape[0]}")
                    return img_rgba
                
                print("[人脸对齐] 检测到二维数组格式")
                left_eye = landmarks[0]  # [x0, y0]
                right_eye = landmarks[1]  # [x1, y1]
                
                # 确保是二维坐标
                if len(left_eye) < 2 or len(right_eye) < 2:
                    print(f"[人脸对齐] 眼睛坐标维度不对")
                    return img_rgba
            else:
                print(f"[人脸对齐] landmarks维度错误: {landmarks.ndim}")
                return img_rgba
            
            # 计算角度
            delta_x = float(right_eye[0] - left_eye[0])
            delta_y = float(right_eye[1] - left_eye[1])
            angle = np.degrees(np.arctan2(delta_y, delta_x))
            
            print(f"[人脸对齐] 左眼: {left_eye}, 右眼: {right_eye}")
            print(f"[人脸对齐] 计算角度: {angle:.2f}°")
            
            # 如果角度很小，不需要旋转
            if abs(angle) < 0.5:
                print(f"[人脸对齐] 角度太小，跳过旋转")
                return img_rgba
            
            # 计算旋转中心（两眼中点）
            center_x = (float(left_eye[0]) + float(right_eye[0])) / 2
            center_y = (float(left_eye[1]) + float(right_eye[1])) / 2
            center = (int(center_x), int(center_y))
            
            # 获取旋转矩阵
            h, w = img_rgba.shape[:2]
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            
            # 旋转图像
            rotated = cv2.warpAffine(
                img_rgba, 
                rotation_matrix, 
                (w, h), 
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0)  # 透明背景
            )
            
            print(f"[人脸对齐] 旋转成功，角度: {angle:.2f}°")
            return rotated
            
        except Exception as e:
            print(f"[人脸对齐] 处理异常: {e}")
            import traceback
            traceback.print_exc()
            return img_rgba
    
    def _apply_solid_background(self, img_rgba: np.ndarray, color: tuple) -> np.ndarray:
        """应用纯色背景"""
        h, w = img_rgba.shape[:2]
        
        # 创建背景
        background = np.zeros((h, w, 3), dtype=np.uint8)
        background[:] = color  # BGR格式
        
        # 获取alpha通道
        if img_rgba.shape[2] == 4:
            alpha = img_rgba[:, :, 3] / 255.0
            rgb = img_rgba[:, :, :3]
        else:
            # 没有alpha通道，直接返回
            return img_rgba
        
        # 混合前景和背景
        for c in range(3):
            background[:, :, c] = (alpha * rgb[:, :, c] + (1 - alpha) * background[:, :, c]).astype(np.uint8)
        
        return background
    
    def _apply_gradient_background(self, img_rgba: np.ndarray) -> np.ndarray:
        """
        应用渐变背景（完全按照官方实现）
        官方参考：hivision/utils.py 的 generate_gradient 和 add_background
        """
        h, w = img_rgba.shape[:2]
        
        # 获取渲染模式
        render_map = {
            "纯色": "pure_color",
            "上下渐变（白色）": "updown_gradient",
            "中心渐变（白色）": "center_gradient",
        }
        
        if hasattr(self, 'render_combo'):
            render_text = self.render_combo.currentText()
            mode = render_map.get(render_text, "pure_color")
        else:
            mode = "pure_color"
        
        # 获取背景颜色
        bg_name = self.bg_combo.currentText() if hasattr(self, 'bg_combo') else '白色'
        if bg_name == '自定义(RGB)' or bg_name == '自定义(HEX)':
            start_color = self.custom_color
        else:
            start_color = self.bg_colors.get(bg_name, (255, 255, 255))
        
        # 分离通道
        if img_rgba.shape[2] == 4:
            b, g, r, a = cv2.split(img_rgba)
        else:
            return img_rgba
        
        a_cal = a / 255.0
        
        if mode == "pure_color":
            # 纯色填充
            b2 = np.full([h, w], start_color[0], dtype=np.float32)
            g2 = np.full([h, w], start_color[1], dtype=np.float32)
            r2 = np.full([h, w], start_color[2], dtype=np.float32)
        
        elif mode == "updown_gradient":
            # 上下渐变（官方算法）
            end_color = (255, 255, 255)  # 白色
            r2 = np.zeros((h, w), dtype=np.float32)
            g2 = np.zeros((h, w), dtype=np.float32)
            b2 = np.zeros((h, w), dtype=np.float32)
            
            for y in range(h):
                ratio = y / h
                r2[y, :] = ratio * end_color[0] + (1 - ratio) * start_color[2]  # BGR->RGB
                g2[y, :] = ratio * end_color[1] + (1 - ratio) * start_color[1]
                b2[y, :] = ratio * end_color[2] + (1 - ratio) * start_color[0]  # BGR->RGB
        
        else:  # center_gradient
            # 中心渐变（官方算法）
            end_color = (255, 255, 255)  # 白色
            img_bg = np.zeros((h, w, 3), dtype=np.uint8)
            center = (w // 2, h // 2)
            end_axes = max(h, w)
            
            for y in range(end_axes):
                axes = (end_axes - y, end_axes - y)
                ratio = y / end_axes
                # BGR格式
                color_b = int(ratio * end_color[2] + (1 - ratio) * start_color[0])
                color_g = int(ratio * end_color[1] + (1 - ratio) * start_color[1])
                color_r = int(ratio * end_color[0] + (1 - ratio) * start_color[2])
                cv2.ellipse(img_bg, center, axes, 0, 0, 360, (color_b, color_g, color_r), -1)
            
            b2, g2, r2 = cv2.split(img_bg.astype(np.float32))
        
        # 官方混合公式：(foreground - background) * alpha + background
        output = cv2.merge([
            ((b - b2) * a_cal + b2).astype(np.uint8),
            ((g - g2) * a_cal + g2).astype(np.uint8),
            ((r - r2) * a_cal + r2).astype(np.uint8)
        ])
        
        return output
    
    def _analyze_photo_characteristics(self, img_rgba: np.ndarray, face_info: dict, person_bounds: dict) -> dict:
        """
        分析原图特征，判断拍摄情况
        
        Args:
            img_rgba: 原图（RGBA格式）
            face_info: 人脸检测结果
            person_bounds: 人体边界
            
        Returns:
            dict: {
                'shot_type': 'close_up' | 'half_body' | 'full_body',  # 拍摄类型
                'head_height': int,        # 头部高度（像素）
                'total_height': int,       # 人体总高度（像素）
                'head_ratio': float,       # 头部占人体的比例
                'body_ratio': float,       # 身体部分占整体的比例
                'recommended_measure': float,  # 推荐的 head_measure_ratio
                'recommended_top_distance': float,  # 推荐的 top_distance
            }
        """
        head_top = face_info['head_top']
        chin = face_info['chin']
        person_bottom = person_bounds['bottom']
        
        # 1. 计算头部高度和人体总高度
        head_height = chin - head_top
        total_height = person_bottom - head_top
        
        # 防止除零
        if total_height <= 0:
            total_height = head_height * 2
        
        # 2. 判断拍摄类型
        head_body_ratio = head_height / total_height if total_height > 0 else 0.5
        
        if head_body_ratio > 0.65:  # 头部占比 > 65%
            shot_type = 'close_up'      # 特写（只有头和一点肩膀）
            recommended_measure = 0.15  # 让照片包含更多内容
            recommended_top_distance = 0.08
            
        elif head_body_ratio > 0.35:  # 头部占比 35%-65%
            shot_type = 'half_body'     # 半身照（到腰部或更多）
            recommended_measure = 0.2   # 默认值
            recommended_top_distance = 0.12
            
        else:  # 头部占比 < 35%
            shot_type = 'full_body'     # 全身照
            recommended_measure = 0.3   # 放大头部
            recommended_top_distance = 0.15
        
        return {
            'shot_type': shot_type,
            'head_height': head_height,
            'total_height': total_height,
            'head_ratio': head_body_ratio,
            'body_ratio': 1 - head_body_ratio,
            'recommended_measure': recommended_measure,
            'recommended_top_distance': recommended_top_distance,
        }
    
    def _adjust_for_id_type(self, base_params: dict, id_type_name: str) -> tuple:
        """
        根据证件照类型微调参数
        
        不同证件照的要求：
        - 一寸照：需要大头，少肩膀 (头占比 70-75%)
        - 身份证/社保卡：需要露出锁骨，肩膀要明显 (头占比 60-65%)
        - 护照：标准照 (头占比 60-70%)
        - 签证照：各国要求不同
          * 美国：头占比 50-70%
          * 日本/韩国：头占比 70%
        
        Args:
            base_params: 基础参数（从拍摄类型分析得到）
            id_type_name: 证件照类型名称
            
        Returns:
            (head_measure_ratio, top_distance_max, top_distance_min)
        """
        measure = base_params['recommended_measure']
        top_dist = base_params['recommended_top_distance']
        
        # 提取证件照类型关键词
        id_lower = id_type_name.lower()
        
        # ===== 一寸/二寸系列：大头照 =====
        if any(kw in id_lower for kw in ['一寸', '二寸', '教师资格', '公务员', '会计']):
            measure *= 1.3   # 增大头部 30%
            top_dist *= 0.8  # 头顶更近 20%
        
        # ===== 身份证/社保卡：需要露出锁骨 =====
        elif any(kw in id_lower for kw in ['身份证', '社保卡']):
            measure *= 0.8   # 减小头部 20%，增加肩膀
            top_dist *= 0.9  # 头顶稍近 10%
        
        # ===== 驾驶证：与身份证类似 =====
        elif '驾驶证' in id_lower:
            measure *= 0.85  # 减小头部 15%
            top_dist *= 0.95
        
        # ===== 中国护照：标准照 =====
        elif '中国护照' in id_lower or '护照' in id_lower:
            measure *= 1.0   # 保持标准
            top_dist *= 1.0
        
        # ===== 美国签证：头占比 50-70% =====
        elif '美国签证' in id_lower:
            measure *= 0.9   # 稍小头部
            top_dist *= 1.1  # 头顶留白更多
        
        # ===== 日本/韩国签证：头占比 70% =====
        elif any(kw in id_lower for kw in ['日本签证', '韩国签证']):
            measure *= 1.2   # 增大头部 20%
            top_dist *= 0.85 # 头顶更近 15%
        
        # ===== 四六级/计算机等级考试：头占比 70% =====
        elif any(kw in id_lower for kw in ['四六级', '计算机等级', '研究生']):
            measure *= 1.25  # 增大头部 25%
            top_dist *= 0.82
        
        # ===== 其他：保持默认 =====
        else:
            pass
        
        # 确保参数在合理范围内
        measure = max(0.1, min(0.5, measure))
        top_dist = max(0.02, min(0.25, top_dist))
        top_dist_min = max(0.02, top_dist - 0.02)
        
        return (measure, top_dist, top_dist_min)
    
    def _detect_face(self, img: np.ndarray, method: str = 'auto') -> dict:
        """
        检测人脸（支持多种检测器）
        参考 HivisionIDPhotos 官方实现
        
        Args:
            img: 输入图像
            method: 检测方法 ('auto', 'mtcnn', 'retinaface', 'opencv')
        
        Returns:
            dict: {
                'face_top': 人脸框顶部（眉毛位置）,
                'face_bottom': 人脸框底部（下巴位置）,
                'face_left': 人脸框左边,
                'face_right': 人脸框右边,
                'head_top': 估算的头顶位置,
                'chin': 下巴位置,
                'center_x': 人脸中心X,
                'head_height': 头部高度（头顶到下巴）,
                'roll_angle': 人脸旋转角度,
                'landmarks': 人脸关键点,
                'method': 检测方法
            }
            如果检测失败返回 None
        """
        from utils.face_detector import detect_face
        
        # 使用统一的人脸检测
        face_result = detect_face(img, method=method)
        # 指定方法失败时回退到 auto，确保仍有 face 信息用于裁剪/排版
        if face_result is None and method != 'auto':
            face_result = detect_face(img, method='auto')
        if face_result is None:
            return None
        
        # 转换格式以兼容现有代码
        left, top, w, h = face_result['rectangle']
        
        face_top = top
        face_bottom = top + h
        face_left = left
        face_right = left + w
        
        # 估算头顶位置：人脸框上方扩展
        forehead_height = int(h * self.FOREHEAD_EXTENSION)
        head_top = max(0, face_top - forehead_height)
        
        # 头部高度 = 头顶到下巴
        head_height = face_bottom - head_top
        
        # 人脸中心X
        center_x = left + w // 2
        
        result = {
            'face_top': face_top,
            'face_bottom': face_bottom,
            'face_left': face_left,
            'face_right': face_right,
            'head_top': head_top,
            'chin': face_bottom,
            'center_x': center_x,
            'head_height': head_height,
            'face_width': w,
            'face_height': h,
            'roll_angle': face_result.get('roll_angle', 0.0),
            'method': face_result.get('method', 'Unknown')
        }
        
        # 如果有关键点，也保存
        if 'landmarks' in face_result:
            result['landmarks'] = face_result['landmarks']
        
        return result
    
    def _analyze_person_bounds(self, img_rgba: np.ndarray) -> dict:
        """分析抠图结果，找到人体边界（头顶、底部、左右）+ 人脸检测"""
        if img_rgba.shape[2] != 4:
            return None
        
        alpha = img_rgba[:, :, 3]
        h, w = alpha.shape
        
        # 找到有内容的区域（alpha > 128 认为是前景）
        mask = alpha > 128
        
        if not mask.any():
            return None
        
        # 找到人体边界
        rows_with_content = np.any(mask, axis=1)
        cols_with_content = np.any(mask, axis=0)
        
        top = np.argmax(rows_with_content)  # 头顶位置
        bottom = h - np.argmax(rows_with_content[::-1]) - 1  # 底部位置
        left = np.argmax(cols_with_content)  # 左边界
        right = w - np.argmax(cols_with_content[::-1]) - 1  # 右边界
        
        # 计算人体中心
        center_x = (left + right) // 2
        center_y = (top + bottom) // 2
        
        # 尝试检测人脸获取更精确的位置（使用指定的检测器）
        face_info = self._detect_face(img_rgba, method=self.face_detect_model)
        
        result = {
            'top': top,
            'bottom': bottom,
            'left': left,
            'right': right,
            'center_x': center_x,
            'center_y': center_y,
            'height': bottom - top,
            'width': right - left,
            'face_info': face_info  # 可能为None
        }
        
        return result
    
    def _crop_to_size(self, img: np.ndarray, target_size: tuple, person_bounds: dict = None) -> np.ndarray:
        """
        裁剪到标准尺寸，严格按照中国证件照标准：
        - 头部高度（头顶到下巴）占照片高度的 58%-69%，取 63%
        - 头顶到照片上边缘约 6%-10%，取 8%
        - 人脸水平居中
        
        Args:
            img: 输入图片（已抠图换背景）
            target_size: 目标尺寸 (width, height)
            person_bounds: 人体边界信息（包含face_info）
        
        Returns:
            裁剪后的标准证件照
        """
        target_w, target_h = target_size
        img_h, img_w = img.shape[:2]
        
        # 获取人脸信息
        face_info = None
        if person_bounds and person_bounds.get('face_info'):
            face_info = person_bounds['face_info']
        
        if face_info:
            # ===== 有人脸检测结果，按标准比例裁剪 =====
            head_top = face_info['head_top']  # 估算的头顶
            chin = face_info['chin']  # 下巴
            center_x = face_info['center_x']  # 人脸中心X
            head_height = face_info['head_height']  # 头部高度
            
            # 目标：头部高度占照片高度的 HEAD_HEIGHT_RATIO (63%)
            # 计算需要的照片高度（在原图尺度）
            desired_photo_height = head_height / self.HEAD_HEIGHT_RATIO
            
            # 目标：头顶到照片上边缘占 TOP_MARGIN_RATIO (8%)
            top_margin = desired_photo_height * self.TOP_MARGIN_RATIO
            
            # 计算裁剪区域（在原图尺度）
            # 照片顶部 = 头顶 - 上边距
            crop_top = head_top - top_margin
            crop_bottom = crop_top + desired_photo_height
            
            # 计算宽度（保持目标宽高比）
            target_ratio = target_w / target_h
            desired_photo_width = desired_photo_height * target_ratio
            
            # 水平居中于人脸
            crop_left = center_x - desired_photo_width / 2
            crop_right = crop_left + desired_photo_width
            
            # 边界检查和调整
            # 如果裁剪区域超出图片，需要调整
            if crop_top < 0:
                # 头顶空间不够，向下移动整个区域
                offset = -crop_top
                crop_top = 0
                crop_bottom = min(img_h, crop_bottom + offset)
            
            if crop_bottom > img_h:
                # 底部空间不够，尝试缩小或向上移动
                crop_bottom = img_h
                # 重新计算顶部，但保持比例
                actual_height = crop_bottom - crop_top
                if actual_height < desired_photo_height * 0.8:
                    # 高度不够，使用整图高度
                    crop_top = 0
                    crop_bottom = img_h
            
            if crop_left < 0:
                crop_left = 0
                crop_right = min(img_w, desired_photo_width)
            
            if crop_right > img_w:
                crop_right = img_w
                crop_left = max(0, crop_right - desired_photo_width)
            
            # 转换为整数
            crop_top = int(max(0, crop_top))
            crop_bottom = int(min(img_h, crop_bottom))
            crop_left = int(max(0, crop_left))
            crop_right = int(min(img_w, crop_right))
            
            # 确保裁剪区域有效
            if crop_right <= crop_left or crop_bottom <= crop_top:
                # 退回到简单裁剪
                return self._simple_crop(img, target_size, person_bounds)
            
            # 裁剪
            cropped = img[crop_top:crop_bottom, crop_left:crop_right]
            
            # 缩放到目标尺寸（保持宽高比，可能需要填充）
            crop_h, crop_w = cropped.shape[:2]
            crop_ratio = crop_w / crop_h
            
            if abs(crop_ratio - target_ratio) < 0.01:
                # 比例接近，直接缩放
                result = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
            else:
                # 比例不同，需要在目标尺寸内居中放置
                # 计算缩放比例
                scale = min(target_w / crop_w, target_h / crop_h)
                new_w = int(crop_w * scale)
                new_h = int(crop_h * scale)
                
                resized = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
                
                # 创建目标大小的画布（使用背景色填充）
                # 检测背景色（取左上角像素）
                bg_color = tuple(img[0, 0].tolist()[:3]) if len(img.shape) == 3 else (255, 255, 255)
                result = np.full((target_h, target_w, 3), bg_color, dtype=np.uint8)
                
                # 居中放置
                x_offset = (target_w - new_w) // 2
                y_offset = (target_h - new_h) // 2
                result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized[:, :, :3] if resized.shape[2] > 3 else resized
        
        else:
            # ===== 没有人脸检测结果，使用简单裁剪 =====
            result = self._simple_crop(img, target_size, person_bounds)
        
        # 对小尺寸输出进行轻微锐化
        if target_w < 500 or target_h < 500:
            result = self._sharpen_image(result)
        
        return result
    
    def _simple_crop(self, img: np.ndarray, target_size: tuple, person_bounds: dict = None) -> np.ndarray:
        """
        简单裁剪（当人脸检测失败时的备选方案）
        基于人体边界进行裁剪
        """
        target_w, target_h = target_size
        h, w = img.shape[:2]
        target_ratio = target_w / target_h
        
        if person_bounds is not None:
            head_top = person_bounds['top']
            center_x = person_bounds['center_x']
            person_height = person_bounds['height']
            
            # 估算：人体高度约为照片高度的70-80%
            desired_photo_height = person_height / 0.75
            top_margin = desired_photo_height * 0.08
        else:
            head_top = 0
            center_x = w // 2
            desired_photo_height = h
            top_margin = 0
        
        # 计算缩放比例
        scale = target_h / desired_photo_height if desired_photo_height > 0 else 1.0
        scale = max(scale, target_w / w)  # 确保宽度也够
        
        # 缩放图片
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        if scale < 1:
            resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        # 计算裁剪位置
        scaled_head_top = int(head_top * scale)
        scaled_center_x = int(center_x * scale)
        scaled_top_margin = int(top_margin * scale)
        
        start_y = max(0, scaled_head_top - scaled_top_margin)
        start_x = max(0, scaled_center_x - target_w // 2)
        
        # 确保不超出边界
        start_x = max(0, min(start_x, new_w - target_w))
        start_y = max(0, min(start_y, new_h - target_h))
        
        # 如果图片不够大，需要填充
        if new_w < target_w or new_h < target_h:
            bg_color = tuple(img[0, 0].tolist()[:3]) if len(img.shape) == 3 else (255, 255, 255)
            result = np.full((target_h, target_w, 3), bg_color, dtype=np.uint8)
            
            x_offset = max(0, (target_w - new_w) // 2)
            y_offset = max(0, (target_h - new_h) // 2)
            
            paste_w = min(new_w, target_w)
            paste_h = min(new_h, target_h)
            
            src = resized[:paste_h, :paste_w]
            if src.shape[2] > 3:
                src = src[:, :, :3]
            result[y_offset:y_offset+paste_h, x_offset:x_offset+paste_w] = src
            return result
        
        # 裁剪
        cropped = resized[start_y:start_y+target_h, start_x:start_x+target_w]
        
        if cropped.shape[2] > 3:
            cropped = cropped[:, :, :3]
        
        return cropped
    
    def _sharpen_image(self, img: np.ndarray) -> np.ndarray:
        """轻微锐化图片，提升清晰度"""
        if img.shape[2] == 4:
            # RGBA图像，只锐化RGB部分
            rgb = img[:, :, :3]
            alpha = img[:, :, 3:4]
            gaussian = cv2.GaussianBlur(rgb, (0, 0), 2.0)
            sharpened_rgb = cv2.addWeighted(rgb, 1.3, gaussian, -0.3, 0)
            return np.concatenate([sharpened_rgb, alpha], axis=2)
        else:
            gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
            sharpened = cv2.addWeighted(img, 1.3, gaussian, -0.3, 0)
            return sharpened
    
    def _apply_beauty_effects(self, img: np.ndarray, whitening: int = 0, brightness: int = 0, 
                             contrast: int = 0, saturation: int = 0, sharpen: int = 0) -> np.ndarray:
        """
        应用美颜效果（完全按照 HivisionIDPhotos 官方实现）
        参考：hivision/creator/photo_processor.py
        
        Args:
            img: BGR或RGBA图像
            whitening: 美白强度 0-15
            brightness: 亮度调整 -5~+25
            contrast: 对比度调整 -10~+50  
            saturation: 饱和度调整 -10~+50
            sharpen: 锐化强度 0-5
        
        Returns:
            美颜后的图像
        """
        if all(v == 0 for v in [whitening, brightness, contrast, saturation, sharpen]):
            return img
        
        # 处理RGBA图像
        has_alpha = img.shape[2] == 4
        if has_alpha:
            rgb = img[:, :, :3].copy()
            alpha = img[:, :, 3:4]
        else:
            rgb = img.copy()
            alpha = None
        
        # ===== 1. 美白（Whitening） =====
        if whitening > 0:
            # 官方实现：转换到 LAB 色彩空间，提升 L 通道
            lab = cv2.cvtColor(rgb, cv2.COLOR_BGR2LAB).astype(np.float32)
            l, a, b = cv2.split(lab)
            
            # 美白强度转换：0-15 -> 0-30
            l += whitening * 2
            l = np.clip(l, 0, 255)
            
            lab = cv2.merge([l, a, b])
            rgb = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
        
        # ===== 2. 亮度（Brightness） =====
        if brightness != 0:
            # 官方实现：直接调整像素值
            rgb = rgb.astype(np.float32)
            rgb += brightness
            rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        
        # ===== 3. 对比度（Contrast） =====
        if contrast != 0:
            # 官方实现：使用 alpha 混合
            # contrast: -10~+50 -> factor: 0.5~2.0
            factor = 1.0 + contrast / 50.0
            rgb = rgb.astype(np.float32)
            rgb = (rgb - 127.5) * factor + 127.5
            rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        
        # ===== 4. 饱和度（Saturation） =====
        if saturation != 0:
            # 官方实现：转换到 HSV 色彩空间，调整 S 通道
            hsv = cv2.cvtColor(rgb, cv2.COLOR_BGR2HSV).astype(np.float32)
            h, s, v = cv2.split(hsv)
            
            # 饱和度调整：-10~+50 -> 0.8~2.0
            factor = 1.0 + saturation / 50.0
            s = s * factor
            s = np.clip(s, 0, 255)
            
            hsv = cv2.merge([h, s, v])
            rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        
        # ===== 5. 锐化（Sharpen） =====
        if sharpen > 0:
            # 官方实现：使用高斯模糊 + 加权
            # sharpen: 0-5 -> amount: 0-1.5
            amount = sharpen / 5.0 * 1.5
            
            blurred = cv2.GaussianBlur(rgb, (0, 0), 3)
            rgb = cv2.addWeighted(rgb, 1.0 + amount, blurred, -amount, 0)
            rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        
        # 重新组合alpha通道
        if has_alpha:
            return np.concatenate([rgb, alpha], axis=2)
        return rgb
    
    def _smart_crop_for_id_photo(self, img_rgba: np.ndarray, target_size: tuple, 
                                  person_bounds: dict, original_size: tuple, 
                                  crop_params: tuple = None) -> np.ndarray:
        """
        智能裁剪生成标准证件照（完全按照 HivisionIDPhotos 官方算法）
        参考：hivision/creator/photo_adjuster.py 的 adjust_photo 函数
        
        Args:
            img_rgba: 抠图后的RGBA图像
            target_size: 目标尺寸 (width, height)
            person_bounds: 人体边界信息
            original_size: 原图尺寸 (width, height)
            crop_params: 裁剪参数 (head_measure_ratio, head_height_ratio, head_top_range)
        
        Returns:
            标准证件照RGBA图像
        """
        target_w, target_h = target_size
        img_h, img_w = img_rgba.shape[:2]
        
        # 获取裁剪参数（如果没有传入，使用默认值）
        if crop_params:
            head_measure_ratio, head_height_ratio, head_top_range = crop_params
        else:
            # 使用默认参数
            head_measure_ratio = self.HEAD_MEASURE_RATIO
            head_height_ratio = self.HEAD_HEIGHT_RATIO
            head_top_range = self.HEAD_TOP_RANGE
        
        # 获取人脸信息
        face_info = None
        if person_bounds and person_bounds.get('face_info'):
            face_info = person_bounds['face_info']
        
        if not face_info:
            # 无人脸检测，简单缩放居中
            scale = min(target_w * 0.85 / img_w, target_h * 0.85 / img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            scaled_img = cv2.resize(img_rgba, (new_w, new_h), interpolation=cv2.INTER_AREA)
            result = np.zeros((target_h, target_w, 4), dtype=np.uint8)
            offset_x = (target_w - new_w) // 2
            offset_y = (target_h - new_h) // 2
            result[offset_y:offset_y+new_h, offset_x:offset_x+new_w] = scaled_img
            return result
        
        # ===== 官方算法：基于人脸面积和位置裁剪 =====
        # Step1. 准备人脸参数
        face_x = face_info.get('face_left', 0)
        face_y = face_info.get('face_top', 0)
        face_w = face_info.get('face_width', 0)
        face_h = face_info.get('face_height', 0)
        
        # Step2. 计算高级参数
        face_center_x = face_x + face_w / 2  # 面部中心X坐标
        face_center_y = face_y + face_h / 2  # 面部中心Y坐标
        face_measure = face_w * face_h  # 面部面积
        
        # 裁剪框面积：为面部面积 / head_measure_ratio
        crop_measure = face_measure / head_measure_ratio
        
        # 裁剪框缩放率
        import math
        resize_ratio = crop_measure / (target_h * target_w)
        resize_ratio_single = math.sqrt(resize_ratio)  # 长和宽的缩放率
        
        # 裁剪框大小（在原图尺度）
        crop_h = int(target_h * resize_ratio_single)
        crop_w = int(target_w * resize_ratio_single)
        
        # Step3. 裁剪框的定位信息
        # 水平居中于人脸
        x1 = int(face_center_x - crop_w / 2)
        # 人脸中心在裁剪框高度的 head_height_ratio 位置
        y1 = int(face_center_y - crop_h * head_height_ratio)
        x2 = x1 + crop_w
        y2 = y1 + crop_h
        
        # Step4. 裁剪（处理边界超出）
        cropped = self._idphoto_cut(x1, y1, x2, y2, img_rgba)
        cropped = cv2.resize(cropped, (crop_w, crop_h), interpolation=cv2.INTER_AREA)
        
        # Step5. 检测人像位置是否合理
        y_top, y_bottom, x_left, x_right = self._get_box(cropped)
        
        # 检测左右是否有空隙
        width_height_ratio = target_w / target_h
        if x_left > 0 or x_right > 0:
            cut_value_top = int(((x_left + x_right) * width_height_ratio) / 2)
        else:
            cut_value_top = 0
        
        # 检测头顶距离是否合适
        status_top, move_value = self._detect_distance(
            y_top - cut_value_top,
            crop_h,
            max_ratio=head_top_range[0],
            min_ratio=head_top_range[1]
        )
        
        # Step6. 第二轮裁剪（调整位置）
        if x_left == 0 and x_right == 0 and status_top == 0:
            result_image = cropped
        else:
            result_image = self._idphoto_cut(
                x1 + x_left,
                y1 + cut_value_top + status_top * move_value,
                x2 - x_right,
                y2 - cut_value_top + status_top * move_value,
                img_rgba
            )
        
        # Step7. 底部空隙处理（下拉至底部）
        result_image = self._move_bottom(result_image)
        
        # Step8. 缩放到目标尺寸（官方渐进式缩放）
        result = self._standard_photo_resize(result_image, (target_h, target_w))
        
        return result
    
    # ===== HivisionIDPhotos 官方辅助方法 =====
    
    def _idphoto_cut(self, x1, y1, x2, y2, img):
        """
        官方裁剪函数（处理边界超出）
        参考：hivision/creator/photo_adjuster.py 的 IDphotos_cut
        """
        crop_size = (y2 - y1, x2 - x1)
        
        temp_x_1 = 0
        temp_y_1 = 0
        temp_x_2 = 0
        temp_y_2 = 0

        if y1 < 0:
            temp_y_1 = abs(y1)
            y1 = 0
        if y2 > img.shape[0]:
            temp_y_2 = y2
            y2 = img.shape[0]
            temp_y_2 = temp_y_2 - y2

        if x1 < 0:
            temp_x_1 = abs(x1)
            x1 = 0
        if x2 > img.shape[1]:
            temp_x_2 = x2
            x2 = img.shape[1]
            temp_x_2 = temp_x_2 - x2

        # 生成一张全透明背景
        background_bgr = np.full((crop_size[0], crop_size[1]), 255, dtype=np.uint8)
        background_a = np.full((crop_size[0], crop_size[1]), 0, dtype=np.uint8)
        background = cv2.merge(
            (background_bgr, background_bgr, background_bgr, background_a)
        )

        background[
            temp_y_1 : crop_size[0] - temp_y_2, temp_x_1 : crop_size[1] - temp_x_2
        ] = img[y1:y2, x1:x2]

        return background
    
    def _get_box(self, image, thresh=127):
        """
        官方 get_box 函数（获取人像边界）
        参考：hivision/creator/utils.py 的 get_box
        返回 model=2 模式：[y_top_distance, y_bottom_distance, x_left_distance, x_right_distance]
        """
        if len(image.shape) == 2 or image.shape[2] != 4:
            return [0, 0, 0, 0]
        
        # 分离 mask
        _, _, _, mask = cv2.split(image)
        # mask 二值化处理
        _, mask = cv2.threshold(mask, thresh=thresh, maxval=255, type=0)
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return [0, 0, 0, 0]
        
        contours_area = []
        for cnt in contours:
            contours_area.append(cv2.contourArea(cnt))
        idx = contours_area.index(max(contours_area))
        x, y, w, h = cv2.boundingRect(contours[idx])
        
        # 返回矩形框四边相距于原图四边的距离
        height, width, _ = image.shape
        y_up = y
        y_down = height - (y + h)
        x_left = x
        x_right = width - (x + w)
        
        return [y_up, y_down, x_left, x_right]
    
    def _detect_distance(self, value, crop_height, max_ratio=0.12, min_ratio=0.1):
        """
        官方距离检测函数
        参考：hivision/creator/utils.py 的 detect_distance
        检测人头顶与照片顶部的距离是否在适当范围内
        
        Returns:
            (status, move_value)
            status=0 不动
            status=1 人脸应向上移动（裁剪框向下移动）
            status=-1 人脸应向下移动（裁剪框向上移动）
        """
        value = value / crop_height  # 头顶往上的像素占图像的比例
        if min_ratio <= value <= max_ratio:
            return 0, 0
        elif value > max_ratio:
            # 头顶往上的像素比例高于 max
            move_value = value - max_ratio
            move_value = int(move_value * crop_height)
            return 1, move_value
        else:
            # 头顶往上的像素比例低于 min
            move_value = min_ratio - value
            move_value = int(move_value * crop_height)
            return -1, move_value
    
    def _move_bottom(self, input_image):
        """
        官方底部移动函数
        参考：hivision/creator/photo_adjuster.py 的 move
        当照片底部存在空隙时，下拉至底部
        """
        png_img = input_image.astype(np.uint8)
        height, width, channels = png_img.shape
        y_low, y_high, _, _ = self._get_box(png_img)
        
        if y_high == 0:
            return png_img
        
        base = np.zeros((y_high, width, channels), dtype=np.uint8)
        png_img = png_img[0 : height - y_high, :, :]
        png_img = np.concatenate((base, png_img), axis=0)
        return png_img
    
    def _standard_photo_resize(self, input_image, size):
        """
        官方标准照缩放函数
        参考：hivision/creator/photo_adjuster.py 的 standard_photo_resize
        
        Args:
            input_image: 输入图像（高清照）
            size: 标准照的尺寸 (height, width)
        """
        resize_ratio = input_image.shape[0] / size[0]
        resize_item = int(round(input_image.shape[0] / size[0]))
        
        if resize_ratio >= 2:
            # 多次渐进式缩放
            for i in range(resize_item - 1):
                if i == 0:
                    result_image = cv2.resize(
                        input_image,
                        (size[1] * (resize_item - i - 1), size[0] * (resize_item - i - 1)),
                        interpolation=cv2.INTER_AREA,
                    )
                else:
                    result_image = cv2.resize(
                        result_image,
                        (size[1] * (resize_item - i - 1), size[0] * (resize_item - i - 1)),
                        interpolation=cv2.INTER_AREA,
                    )
            # 最后一次缩放到目标尺寸
            result_image = cv2.resize(
                result_image, (size[1], size[0]), interpolation=cv2.INTER_AREA
            )
        else:
            # 一次性缩放
            result_image = cv2.resize(
                input_image, (size[1], size[0]), interpolation=cv2.INTER_AREA
            )
        
        return result_image
    
    def create_print_layout(self, photo_path: str, paper_type: str = '6寸', 
                           count: int = None, gap_mm: float = 2.5, 
                           show_crop_line: bool = False, for_preview: bool = False) -> str:
        """
        生成排版打印图（完全按照 HivisionIDPhotos 官方实现）
        官方参考：hivision/creator/layout_calculator.py
        
        Args:
            photo_path: 单张证件照路径（BGR格式）
            paper_type: '6寸' 或 'A4'
            count: 排版张数（None=自动最大化利用纸张）
            gap_mm: 照片间距（毫米）
            show_crop_line: 是否显示裁剪线
            for_preview: 保留参数（兼容性，不再使用）
        
        Returns:
            排版图路径
        """
        # 纸张尺寸 (宽×高, 像素 @300dpi)
        # 标准相纸尺寸规格：
        # 3R = 3.5x5 inch = 89x127mm = 1050x1500px
        # 4R = 4x6 inch = 102x152mm = 1205x1795px
        # 5R = 5x7 inch = 127x178mm = 1500x2100px
        # 6R = 6x8 inch = 152x203mm = 1795x2398px
        # A4 = 210x297mm = 2480x3508px
        PAPER_SIZES = {
            '6寸': (1795, 2398),   # 6寸 = 6R = 152x203mm
            '六寸': (1795, 2398),  # 中文别名
            '5寸': (1500, 2100),   # 5寸 = 5R = 127x178mm
            '五寸': (1500, 2100),  # 中文别名
            'A4': (2480, 3508),    # A4纸竖向 = 210x297mm
            '3R': (1050, 1500),    # 3R = 3.5x5 inch = 89x127mm
            '4R': (1200, 1800),    # 4R = 4x6 inch = 102x152mm (标准300dpi: 1200×1800px，修正为更准确的尺寸)
        }
        
        # 300dpi下1mm对应的像素
        MM_TO_PX = 300 / 25.4  # 约11.81像素/毫米
        
        # 读取照片（支持中文路径）
        photo = cv2_imread(photo_path, cv2.IMREAD_COLOR)
        if photo is None:
            raise RuntimeError("无法读取证件照")
        
        photo_h, photo_w = photo.shape[:2]
        
        paper_w, paper_h = PAPER_SIZES.get(paper_type, PAPER_SIZES['六寸'])  # 默认使用六寸
        
        # 调试信息：打印纸张尺寸
        print(f"[排版] 纸张类型: {paper_type}, 尺寸: {paper_w}x{paper_h}px, 照片: {photo_w}x{photo_h}px")
        
        # 官方边距参数（按照HivisionIDPhotos标准）
        photo_interval_h = int(gap_mm * MM_TO_PX)  # 照片垂直间距
        photo_interval_w = int(gap_mm * MM_TO_PX)  # 照片水平间距
        sides_interval_h = int(4.2 * MM_TO_PX)    # 上下边距约50px
        sides_interval_w = int(5.9 * MM_TO_PX)    # 左右边距约70px
        
        # 对于较小的纸张（如4R、3R），如果标准边距导致放不下目标数量的标准布局，适当减小边距
        # 先计算标准边距下的可用区域
        temp_limit_w = paper_w - 2 * sides_interval_w
        temp_limit_h = paper_h - 2 * sides_interval_h
        
        # 检查是否能放下目标数量的标准布局（4列×2行用于8张）
        if count == 8:
            needed_w = photo_w * 4 + photo_interval_w * 3
            needed_h = photo_h * 2 + photo_interval_h * 1
            if needed_w > temp_limit_w or needed_h > temp_limit_h:
                # 放不下，减小边距（针对4R、3R等较小纸张）
                if paper_type in ['4R', '3R']:
                    # 尝试减小边距，直到能放下4列×2行
                    for test_margin in [3.5, 3.0, 2.5, 2.0, 1.5]:
                        test_sides_w = int(test_margin * MM_TO_PX)
                        test_sides_h = int(test_margin * MM_TO_PX)
                        test_limit_w = paper_w - 2 * test_sides_w
                        test_limit_h = paper_h - 2 * test_sides_h
                        if needed_w <= test_limit_w and needed_h <= test_limit_h:
                            sides_interval_w = test_sides_w
                            sides_interval_h = test_sides_h
                            print(f"[排版] {paper_type}相纸较小，调整边距到{test_margin}mm以容纳8张照片（4列×2行）")
                            break
        
        limit_block_w = paper_w - 2 * sides_interval_w
        limit_block_h = paper_h - 2 * sides_interval_h
        
        # 官方智能布局算法：自动计算最优排版
        layout_mode, center_w, center_h = self._judge_layout(
            photo_w, photo_h,
            photo_interval_w, photo_interval_h,
            limit_block_w, limit_block_h
        )
        
        cols, rows, rotate_mode = layout_mode
        auto_count = cols * rows
        
        # 验证用户指定的数量是否可行
        if count is not None:
            if count > auto_count:
                # 计算照片的物理尺寸（毫米）
                photo_w_mm = photo_w / MM_TO_PX
                photo_h_mm = photo_h / MM_TO_PX
                paper_w_mm = paper_w / MM_TO_PX
                paper_h_mm = paper_h / MM_TO_PX
                
                error_msg = (
                    f"排版失败：照片尺寸过大，无法在 {paper_type} 相纸上排版 {count} 张\n\n"
                    f"纸张尺寸：{paper_w_mm:.1f}×{paper_h_mm:.1f}mm\n"
                    f"照片尺寸：{photo_w_mm:.1f}×{photo_h_mm:.1f}mm\n"
                    f"间距设置：{gap_mm}mm\n\n"
                    f"当前最多可排版：{auto_count} 张 ({cols}列×{rows}行)\n\n"
                    f"建议解决方案：\n"
                    f"1. 减少排版数量到 {auto_count} 张或以下\n"
                    f"2. 选择更大的纸张（如 A4、五寸、六寸）\n"
                    f"3. 减小照片间距\n"
                    f"4. 使用尺寸更小的证件照规格"
                )
                raise ValueError(error_msg)
            
            if count < auto_count:
                # 根据指定数量，计算最优的行列数组合
                best_cols, best_rows = self._calculate_optimal_layout(count, limit_block_w, limit_block_h, 
                                                                      photo_w, photo_h, photo_interval_w, photo_interval_h, rotate_mode)
                cols, rows = best_cols, best_rows
                # 重新计算居中区域
                center_w = photo_w * cols + photo_interval_w * (cols - 1) if cols > 1 else photo_w * cols
                center_h = photo_h * rows + photo_interval_h * (rows - 1) if rows > 1 else photo_h * rows
                print(f"[排版] 指定数量: {count}张, 重新计算布局: {cols}列 x {rows}行")
            else:
                # count == auto_count，使用自动计算的布局
                print(f"[排版] 指定数量: {count}张，与最大排版数相同，使用: {cols}列 x {rows}行")
        else:
            # 未指定数量，使用自动计算的最大值
            count = auto_count
            print(f"[排版] 自动布局: {cols}列 x {rows}行 = {count}张")
        
        # 生成排版位置数组
        typography_arr = []
        x_start = (paper_w - center_w) // 2
        y_start = (paper_h - center_h) // 2
        
        # 根据是否转置调整照片尺寸
        if rotate_mode == 2:  # 转置排列
            photo_h, photo_w = photo_w, photo_h
            photo = cv2.transpose(photo)
            photo = cv2.flip(photo, 0)  # 垂直镜像
        
        # 计算每张照片的位置
        idx = 0
        for row in range(rows):
            for col in range(cols):
                if idx >= count:
                    break
                x = x_start + col * photo_w + col * photo_interval_w
                y = y_start + row * photo_h + row * photo_interval_h
                typography_arr.append((x, y))
                idx += 1
        
        # 创建白色画布
        canvas = np.ones((paper_h, paper_w, 3), dtype=np.uint8) * 255
        
        # 放置照片
        for x, y in typography_arr:
            canvas[y:y+photo_h, x:x+photo_w] = photo
        
        # 添加裁剪线（官方功能）
        if show_crop_line:
            line_color = (200, 200, 200)  # 浅灰色
            line_thickness = 1
            
            # 收集所有裁剪线位置
            vertical_lines = set()
            horizontal_lines = set()
            
            for x, y in typography_arr:
                vertical_lines.add(x)
                vertical_lines.add(x + photo_w)
                horizontal_lines.add(y)
                horizontal_lines.add(y + photo_h)
            
            # 绘制垂直裁剪线
            for x in vertical_lines:
                cv2.line(canvas, (x, 0), (x, paper_h), line_color, line_thickness)
            
            # 绘制水平裁剪线
            for y in horizontal_lines:
                cv2.line(canvas, (0, y), (paper_w, y), line_color, line_thickness)
        
        # 保存排版图
        output_path = create_temp_file(suffix='.png', prefix='print_layout_')
        # 使用 imencode 支持中文路径
        success, encoded = cv2.imencode('.png', canvas, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        if success:
            with open(output_path, 'wb') as f:
                f.write(encoded.tobytes())
        return output_path
    
    def _judge_layout(self, input_width, input_height,
                     photo_interval_w, photo_interval_h,
                     limit_block_w, limit_block_h):
        """
        智能布局判断算法（完全按照官方实现）
        判断横向排列还是转置排列更优，自动计算最大排版数量
        
        Returns:
            (cols, rows, rotate_mode), center_width, center_height
            rotate_mode: 1=不转置, 2=转置
        """
        # 1. 不转置排列的情况
        layout_col_no_transpose = 0
        layout_row_no_transpose = 0
        center_h_1 = input_height
        center_w_1 = input_width
        
        # 计算垂直方向能放几行（最多3行）
        for i in range(1, 4):
            temp_h = input_height * i + photo_interval_h * (i - 1)
            if temp_h < limit_block_h:
                center_h_1 = temp_h
                layout_row_no_transpose = i
            else:
                break
        
        # 计算水平方向能放几列（最多8列）
        for j in range(1, 9):
            temp_w = input_width * j + photo_interval_w * (j - 1)
            if temp_w < limit_block_w:
                center_w_1 = temp_w
                layout_col_no_transpose = j
            else:
                break
        
        count_no_transpose = layout_row_no_transpose * layout_col_no_transpose
        
        # 2. 转置排列的情况（照片旋转90度）
        layout_col_transpose = 0
        layout_row_transpose = 0
        center_h_2 = input_width
        center_w_2 = input_height
        
        # 计算垂直方向能放几行（使用照片的宽度）
        for i in range(1, 4):
            temp_h = input_width * i + photo_interval_h * (i - 1)
            if temp_h < limit_block_h:
                center_h_2 = temp_h
                layout_row_transpose = i
            else:
                break
        
        # 计算水平方向能放几列（使用照片的高度）
        for j in range(1, 9):
            temp_w = input_height * j + photo_interval_w * (j - 1)
            if temp_w < limit_block_w:
                center_w_2 = temp_w
                layout_col_transpose = j
            else:
                break
        
        count_transpose = layout_row_transpose * layout_col_transpose
        
        # 选择能排版更多照片的方式
        if count_transpose > count_no_transpose:
            return (layout_col_transpose, layout_row_transpose, 2), center_w_2, center_h_2
        else:
            return (layout_col_no_transpose, layout_row_no_transpose, 1), center_w_1, center_h_1
    
    def _calculate_optimal_layout(self, target_count: int, limit_block_w: int, limit_block_h: int,
                                  photo_w: int, photo_h: int, photo_interval_w: int, photo_interval_h: int,
                                  rotate_mode: int) -> tuple:
        """
        根据指定数量计算最优的行列数组合（优先精确匹配目标数量）
        
        Args:
            target_count: 目标照片数量
            limit_block_w, limit_block_h: 可用区域尺寸
            photo_w, photo_h: 照片尺寸（已考虑旋转）
            photo_interval_w, photo_interval_h: 照片间距
            rotate_mode: 旋转模式（1=不转置, 2=转置）
        
        Returns:
            (cols, rows) 最优行列数组合
        """
        best_cols, best_rows = 1, target_count
        best_score = float('inf')
        
        # 遍历所有可能的行列数组合（参考HivisionIDPhotos：最多3行，最多8列）
        max_rows = min(target_count, 3)  # 最多3行（与HivisionIDPhotos一致）
        
        for rows in range(1, max_rows + 1):
            cols = (target_count + rows - 1) // rows  # 向上取整，确保能放下所有照片
            
            # 限制列数（与HivisionIDPhotos一致）
            if cols > 8:
                continue
            
            # 检查是否超出可用区域
            total_w = photo_w * cols + photo_interval_w * (cols - 1) if cols > 1 else photo_w * cols
            total_h = photo_h * rows + photo_interval_h * (rows - 1) if rows > 1 else photo_h * rows
            
            if total_w <= limit_block_w and total_h <= limit_block_h:
                actual_count = cols * rows
                
                # 优先选择精确匹配目标数量的布局
                if actual_count == target_count:
                    # 精确匹配：根据目标数量选择最优布局
                    # 标准排版方案：
                    # - 4张：2列×2行（正方形布局，标准方案）
                    # - 6张：3列×2行（横向布局，标准方案）
                    # - 8张：4列×2行（横向布局，标准方案）
                    # - 其他：优先选择接近正方形的布局，但不超过3行
                    if target_count == 4:
                        # 4张照片：优先2列×2行（正方形）
                        if cols == 2 and rows == 2:
                            score = 0  # 最优
                        else:
                            score = 1000  # 其他方案
                    elif target_count == 6:
                        # 6张照片：优先3列×2行
                        if cols == 3 and rows == 2:
                            score = 0  # 最优
                        else:
                            score = 1000  # 其他方案
                    elif target_count == 8:
                        # 8张照片：优先4列×2行
                        if cols == 4 and rows == 2:
                            score = 0  # 最优
                        else:
                            score = 1000  # 其他方案
                    else:
                        # 其他数量：优先选择接近正方形的布局，但不超过3行
                        aspect_ratio = abs(cols / rows - 1.0)  # 行列比与1的差距
                        row_penalty = rows * 10 if rows > 2 else 0  # 超过2行有轻微惩罚
                        score = aspect_ratio * 1000 + row_penalty
                else:
                    # 不匹配：惩罚分数，优先选择接近目标数量的
                    count_diff = abs(actual_count - target_count)
                    aspect_ratio = abs(cols / rows - 1.0)  # 行列比与1的差距
                    score = count_diff * 10000 + aspect_ratio * 1000  # 数量差异权重最大
                
                if score < best_score:
                    best_score = score
                    best_cols, best_rows = cols, rows
        
        # 如果没找到合适的，返回默认值
        if best_cols == 1 and best_rows == target_count:
            # 尝试单行布局
            if photo_w * target_count + photo_interval_w * (target_count - 1) <= limit_block_w:
                return target_count, 1
        
        return best_cols, best_rows
    
    def _crop_to_size_rgba(self, img_rgba: np.ndarray, target_size: tuple, person_bounds: dict = None) -> np.ndarray:
        """
        裁剪RGBA图像到标准证件照尺寸（保持alpha通道）
        
        核心逻辑：
        1. 根据人脸检测结果确定头部位置和大小
        2. 按照证件照标准计算完整照片区域（必须包含肩膀）
        3. 如果原图区域不够，适当调整；如果原图太大，先缩放再裁剪
        
        证件照标准：
        - 头部（头顶到下巴）占照片高度的 65%
        - 头顶到照片上边缘约 8%
        - 下巴以下（肩膀区域）约 27%，必须露出肩膀
        
        Args:
            img_rgba: RGBA输入图片（已抠图）
            target_size: 目标尺寸 (width, height) 像素
            person_bounds: 人体边界信息（包含face_info）
        
        Returns:
            裁剪后的RGBA图像
        """
        target_w, target_h = target_size
        img_h, img_w = img_rgba.shape[:2]
        target_ratio = target_w / target_h
        
        # 获取人脸和人体信息
        face_info = None
        if person_bounds and person_bounds.get('face_info'):
            face_info = person_bounds['face_info']
        
        if face_info:
            # ===== 有人脸检测结果，按标准比例处理 =====
            head_top = face_info['head_top']      # 估算的头顶位置
            chin = face_info['chin']               # 下巴位置
            center_x = face_info['center_x']       # 人脸中心X
            head_height = face_info['head_height'] # 头部高度（头顶到下巴）
            
            # 计算标准证件照需要的完整照片高度（在原图尺度）
            # 头部占照片高度的 HEAD_HEIGHT_RATIO (65%)
            desired_photo_height = head_height / self.HEAD_HEIGHT_RATIO
            
            # 计算各部分位置
            top_margin = desired_photo_height * self.TOP_MARGIN_RATIO  # 头顶上方空间
            bottom_margin = desired_photo_height * self.BOTTOM_MARGIN_MIN_RATIO  # 下巴下方空间（肩膀）
            
            # 照片区域（在原图坐标系）
            photo_top = head_top - top_margin
            photo_bottom = chin + bottom_margin  # 下巴 + 肩膀空间
            
            # 确保照片高度正确
            actual_photo_height = photo_bottom - photo_top
            if actual_photo_height < desired_photo_height:
                # 如果计算的区域不够高，扩展到需要的高度
                diff = desired_photo_height - actual_photo_height
                photo_bottom += diff
            
            # 根据宽高比计算宽度
            desired_photo_width = desired_photo_height * target_ratio
            photo_left = center_x - desired_photo_width / 2
            photo_right = center_x + desired_photo_width / 2
            
            # ===== 边界检查和调整 =====
            # 检查是否超出原图边界
            need_padding = False
            pad_top, pad_bottom, pad_left, pad_right = 0, 0, 0, 0
            
            if photo_top < 0:
                pad_top = int(-photo_top)
                photo_top = 0
            
            if photo_bottom > img_h:
                # 底部超出，检查是否有足够的人体内容
                if person_bounds and person_bounds.get('bottom'):
                    person_bottom = person_bounds['bottom']
                    if photo_bottom > person_bottom + 50:
                        # 超出人体太多，调整
                        photo_bottom = min(img_h, person_bottom + 50)
                else:
                    photo_bottom = img_h
            
            if photo_left < 0:
                pad_left = int(-photo_left)
                photo_left = 0
            
            if photo_right > img_w:
                pad_right = int(photo_right - img_w)
                photo_right = img_w
            
            # 转换为整数
            crop_top = int(max(0, photo_top))
            crop_bottom = int(min(img_h, photo_bottom))
            crop_left = int(max(0, photo_left))
            crop_right = int(min(img_w, photo_right))
            
            # 检查裁剪区域有效性
            if crop_right <= crop_left or crop_bottom <= crop_top:
                return self._simple_crop_rgba(img_rgba, target_size, person_bounds)
            
            # 裁剪
            cropped = img_rgba[crop_top:crop_bottom, crop_left:crop_right].copy()
            crop_h, crop_w = cropped.shape[:2]
            
            # 如果需要padding（原图不够大）
            if pad_top > 0 or pad_bottom > 0 or pad_left > 0 or pad_right > 0:
                # 创建透明画布
                new_h = crop_h + pad_top + pad_bottom
                new_w = crop_w + pad_left + pad_right
                padded = np.zeros((new_h, new_w, 4), dtype=np.uint8)
                padded[pad_top:pad_top+crop_h, pad_left:pad_left+crop_w] = cropped
                cropped = padded
            
            # 缩放到目标尺寸
            result = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
            
        elif person_bounds:
            # ===== 没有人脸检测结果，使用人体轮廓 =====
            # 基于人体边界进行智能裁剪
            person_top = person_bounds['top']
            person_bottom = person_bounds['bottom']
            person_center_x = person_bounds['center_x']
            person_height = person_bounds['height']
            
            # 估算：人体高度约为照片高度的 80-85%（头+肩膀+部分身体）
            desired_photo_height = person_height / 0.82
            
            # 头顶上方留8%空间
            top_margin = desired_photo_height * 0.08
            
            # 计算照片区域
            photo_top = person_top - top_margin
            photo_bottom = photo_top + desired_photo_height
            
            # 宽度
            desired_photo_width = desired_photo_height * target_ratio
            photo_left = person_center_x - desired_photo_width / 2
            photo_right = person_center_x + desired_photo_width / 2
            
            # 边界调整
            if photo_top < 0:
                photo_top = 0
            if photo_bottom > img_h:
                photo_bottom = img_h
            if photo_left < 0:
                photo_left = 0
            if photo_right > img_w:
                photo_right = img_w
            
            crop_top = int(photo_top)
            crop_bottom = int(photo_bottom)
            crop_left = int(photo_left)
            crop_right = int(photo_right)
            
            if crop_right <= crop_left or crop_bottom <= crop_top:
                return self._simple_crop_rgba(img_rgba, target_size, person_bounds)
            
            cropped = img_rgba[crop_top:crop_bottom, crop_left:crop_right]
            result = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        else:
            # ===== 完全没有检测信息，简单居中裁剪 =====
            result = self._simple_crop_rgba(img_rgba, target_size, person_bounds)
        
        # 对小尺寸输出轻微锐化
        if target_w < 500 or target_h < 500:
            result = self._sharpen_image(result)
        
        return result
    
    def _simple_crop_rgba(self, img_rgba: np.ndarray, target_size: tuple, person_bounds: dict = None) -> np.ndarray:
        """
        简单裁剪RGBA图像（备选方案）
        当人脸检测失败时使用，基于整体图像居中裁剪
        """
        target_w, target_h = target_size
        h, w = img_rgba.shape[:2]
        target_ratio = target_w / target_h
        img_ratio = w / h
        
        if person_bounds is not None:
            # 有人体边界信息，基于人体居中
            person_top = person_bounds['top']
            person_bottom = person_bounds['bottom']
            center_x = person_bounds['center_x']
            person_height = person_bounds['height']
            
            # 人体高度约占照片的80%
            desired_photo_height = person_height / 0.80
            top_margin = desired_photo_height * 0.08
        else:
            # 完全没有信息，假设图片本身就是合适的
            person_top = 0
            center_x = w // 2
            desired_photo_height = h * 0.95
            top_margin = h * 0.05
        
        # 计算缩放比例：使内容适合目标尺寸
        scale = target_h / desired_photo_height if desired_photo_height > 0 else 1.0
        
        # 确保宽度也足够
        desired_photo_width = desired_photo_height * target_ratio
        if desired_photo_width > w:
            scale = max(scale, target_w / w)
        
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # 缩放
        if scale < 1:
            resized = cv2.resize(img_rgba, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            resized = cv2.resize(img_rgba, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        # 计算裁剪起始位置
        scaled_person_top = int(person_top * scale)
        scaled_center_x = int(center_x * scale)
        scaled_top_margin = int(top_margin * scale)
        
        # Y方向：头顶上方留适当空间
        start_y = max(0, scaled_person_top - scaled_top_margin)
        # X方向：以人体中心水平居中
        start_x = max(0, scaled_center_x - target_w // 2)
        
        # 确保不超出边界
        start_x = max(0, min(start_x, new_w - target_w))
        start_y = max(0, min(start_y, new_h - target_h))
        
        # 如果图片不够大，创建透明画布
        if new_w < target_w or new_h < target_h:
            result = np.zeros((target_h, target_w, 4), dtype=np.uint8)
            x_offset = max(0, (target_w - new_w) // 2)
            y_offset = max(0, (target_h - new_h) // 2)
            paste_w = min(new_w, target_w)
            paste_h = min(new_h, target_h)
            result[y_offset:y_offset+paste_h, x_offset:x_offset+paste_w] = resized[:paste_h, :paste_w]
            return result
        
        return resized[start_y:start_y+target_h, start_x:start_x+target_w]
    
    def requires_mask(self) -> bool:
        """不需要mask，自动抠图"""
        return False
    
    def get_ui_widget(self) -> QWidget:
        """返回参数设置UI"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        
        # 使用垂直布局包含两行
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)
        
        # 第一行：模式、背景、尺寸选择
        row1 = QWidget()
        row1.setStyleSheet("background: transparent;")
        layout1 = QHBoxLayout(row1)
        layout1.setContentsMargins(0, 0, 0, 0)
        layout1.setSpacing(8)
        
        # 定义下拉框样式
        combo_style = """
            QComboBox {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 6px 12px;
                padding-right: 30px;
                color: hsl(213, 31%, 91%);
            }
            QComboBox:hover {
                border-color: hsl(215, 20.2%, 65.1%);
            }
            QComboBox::drop-down {
                border: none;
                border-left: 1px solid hsl(217.2, 32.6%, 17.5%);
                background: hsl(217.2, 32.6%, 17.5%);
                width: 25px;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QComboBox::drop-down:hover {
                background: hsl(221.2, 83.2%, 53.3%);
            }
            QComboBox QAbstractItemView {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                selection-background-color: hsl(221.2, 83.2%, 53.3%);
                selection-color: white;
                color: hsl(213, 31%, 91%);
            }
        """
        
        # 模式选择
        mode_label = QLabel("模式:")
        mode_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent;")
        layout1.addWidget(mode_label)
        
        self.mode_combo = StyledComboBox()
        self.mode_combo.addItems(["尺寸列表", "只换底", "自定义(px)", "自定义(mm)"])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setMinimumWidth(130)
        self.mode_combo.setStyleSheet(combo_style)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        layout1.addWidget(self.mode_combo)
        
        # 背景颜色选择
        bg_label = QLabel("背景:")
        bg_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent;")
        layout1.addWidget(bg_label)
        
        self.bg_combo = StyledComboBox()
        self.bg_combo.addItems(list(self.bg_colors.keys()))
        self.bg_combo.setCurrentIndex(0)
        self.bg_combo.setMinimumWidth(80)
        self.bg_combo.setStyleSheet(combo_style)
        layout1.addWidget(self.bg_combo)
        
        # 渲染模式选择
        render_label = QLabel("渲染:")
        render_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent;")
        layout1.addWidget(render_label)
        
        self.render_combo = StyledComboBox()
        self.render_combo.addItems(["纯色", "上下渐变（白色）", "中心渐变（白色）"])
        self.render_combo.setCurrentIndex(0)
        self.render_combo.setMinimumWidth(120)
        self.render_combo.setStyleSheet(combo_style)
        layout1.addWidget(self.render_combo)
        
        # 尺寸选择
        size_label = QLabel("尺寸:")
        size_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent;")
        layout1.addWidget(size_label)
        
        self.size_combo = StyledComboBox()
        self.size_combo.addItems(list(self.sizes.keys()))
        self.size_combo.setCurrentIndex(0)
        self.size_combo.setMinimumWidth(120)
        self.size_combo.setStyleSheet(combo_style)
        layout1.addWidget(self.size_combo)
        
        # ===== 人脸检测选择 =====
        face_detect_label = QLabel("人脸检测:")
        face_detect_label.setStyleSheet("color: hsl(215, 20.2%, 65.1%); background: transparent;")
        layout1.addWidget(face_detect_label)
        
        self.face_detect_combo = StyledComboBox()
        self.face_detect_combo.addItems(["快速模式", "高精度模式"])
        self.face_detect_combo.setCurrentIndex(0)  # 默认 MTCNN
        self.face_detect_combo.setMinimumWidth(140)
        self.face_detect_combo.setMaximumWidth(150)
        self.face_detect_combo.setStyleSheet(combo_style)
        self.face_detect_combo.currentTextChanged.connect(self._on_face_detect_changed)
        layout1.addWidget(self.face_detect_combo)
        
        layout1.addStretch()
        main_layout.addWidget(row1)
        
        # 第二行：功能按钮（大按钮、宽间距）
        row2 = QWidget()
        row2.setStyleSheet("background: transparent;")
        layout2 = QHBoxLayout(row2)
        layout2.setContentsMargins(0, 6, 0, 0)
        layout2.setSpacing(16)  # 按钮间距
        
        # 美颜设置按钮
        beauty_button_style = """
            QPushButton {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 8px;
                padding: 10px 20px;
                color: hsl(213, 31%, 91%);
                font-size: 15px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                border-color: hsl(215, 20.2%, 65.1%);
            }
            QPushButton:pressed {
                background-color: hsl(221.2, 83.2%, 53.3%);
            }
        """
        
        beauty_btn = QPushButton("🌿 美颜设置")
        beauty_btn.setMinimumWidth(120)
        beauty_btn.setStyleSheet(beauty_button_style)
        beauty_btn.clicked.connect(self._show_beauty_dialog)
        layout2.addWidget(beauty_btn)
        
        # 水印按钮
        watermark_btn = QPushButton("📝 水印设置")
        watermark_btn.setMinimumWidth(120)
        watermark_btn.setStyleSheet(beauty_button_style)
        watermark_btn.clicked.connect(self._show_watermark_dialog)
        layout2.addWidget(watermark_btn)
        
        # 输出设置按钮 (KB大小 + DPI)
        output_btn = QPushButton("💾 输出设置")
        output_btn.setMinimumWidth(120)
        output_btn.setStyleSheet(beauty_button_style)
        output_btn.clicked.connect(self._show_output_dialog)
        layout2.addWidget(output_btn)
        
        # 高级参数按钮
        advanced_btn = QPushButton("⚙️ 高级参数")
        advanced_btn.setMinimumWidth(120)
        advanced_btn.setStyleSheet(beauty_button_style)
        advanced_btn.clicked.connect(self._show_advanced_dialog)
        layout2.addWidget(advanced_btn)
        
        # 插件功能按钮
        plugin_btn = QPushButton("🤖 插件功能")
        plugin_btn.setMinimumWidth(120)
        plugin_btn.setStyleSheet(beauty_button_style)
        plugin_btn.clicked.connect(self._show_plugin_dialog)
        layout2.addWidget(plugin_btn)
        
        # 输出类型按钮
        output_type_btn = QPushButton("📸 输出类型")
        output_type_btn.setMinimumWidth(120)
        output_type_btn.setStyleSheet(beauty_button_style)
        output_type_btn.clicked.connect(self._show_output_type_dialog)
        layout2.addWidget(output_type_btn)
        
        # 适应框/实际大小（仅导入大图时显示，高度与前面按钮一致，颜色区分）
        self.fit_actual_btn = QPushButton("适应框")
        self.fit_actual_btn.setMinimumWidth(90)
        self.fit_actual_btn.setVisible(False)
        self.fit_actual_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid hsl(215, 20.2%, 65.1%);
                border-radius: 8px;
                padding: 10px 20px;
                color: hsl(215, 20.2%, 65.1%);
                font-size: 15px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                color: hsl(213, 31%, 91%);
            }
        """)
        self.fit_actual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fit_actual_btn.clicked.connect(self._on_fit_actual_clicked)
        layout2.addWidget(self.fit_actual_btn)
        
        layout2.addStretch()
        main_layout.addWidget(row2)
        
        # 将控件引用存储到widget上
        widget.mode_combo = self.mode_combo
        widget.bg_combo = self.bg_combo
        widget.render_combo = self.render_combo
        widget.size_combo = self.size_combo
        
        return widget
    
    def _on_mode_changed(self, mode_text):
        """模式切换回调（完全按照官方）"""
        mode_map = {
            "尺寸列表": 'size_list',
            "只换底": 'only_change_bg',
            "自定义(px)": 'custom_px',
            "自定义(mm)": 'custom_mm',
        }
        self.mode = mode_map.get(mode_text, 'size_list')
        
        # 根据模式启用/禁用尺寸选择
        if hasattr(self, 'size_combo'):
            self.size_combo.setEnabled(self.mode == 'size_list')
        
        # 如果是自定义模式，显示自定义尺寸对话框
        if self.mode in ['custom_px', 'custom_mm']:
            self._show_custom_size_dialog(self.mode)
    
    def _on_face_detect_changed(self, method_text):
        """人脸检测器切换回调"""
        method_map = {
            "快速模式": 'mtcnn',
            "高精度模式": 'retinaface',
        }
        self.face_detect_model = method_map.get(method_text, 'mtcnn')
        print(f"[证件照] 切换人脸检测器: {self.face_detect_model}")
    
    def _show_custom_size_dialog(self, mode):
        """显示自定义尺寸对话框（官方）"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget, QMessageBox
        from PyQt6.QtGui import QIntValidator
        
        dialog = QDialog()
        dialog.setWindowTitle("自定义尺寸 (" + ("px" if mode == 'custom_px' else "mm") + ")")
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet("""
            QDialog { 
                background-color: hsl(222.2, 84%, 4.9%); 
                color: hsl(213, 31%, 91%); 
            }
            QLabel {
                color: hsl(213, 31%, 91%);
                font-size: 13px;
            }
            QLineEdit { 
                background-color: hsl(224, 71.4%, 4.1%); 
                border: 1px solid hsl(217.2, 32.6%, 17.5%); 
                border-radius: 6px; 
                padding: 8px 12px; 
                color: hsl(213, 31%, 91%);
                font-size: 13px;
                min-height: 36px;
            }
            QLineEdit:focus {
                border: 1px solid hsl(221.2, 83.2%, 53.3%);
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)
        
        # 提示信息
        info = QLabel("⚠️ 提示：宽度不应大于高度，尺寸范围 100-1800")
        info.setStyleSheet("""
            color: hsl(38, 92%, 50%);
            background-color: hsla(38, 92%, 50%, 0.1);
            border: 1px solid hsla(38, 92%, 50%, 0.3);
            border-radius: 6px;
            padding: 10px;
            font-size: 12px;
        """)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # 高度输入行
        height_row = QWidget()
        height_row_layout = QHBoxLayout(height_row)
        height_row_layout.setContentsMargins(0, 0, 0, 0)
        height_row_layout.setSpacing(12)
        
        height_label = QLabel("📌 高度" + (":" if mode == 'custom_px' else " (mm)："))
        height_label.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-weight: bold;
            font-size: 14px;
        """)
        height_label.setFixedWidth(100)
        height_row_layout.addWidget(height_label)
        
        h_edit = QLineEdit(str(self.custom_size[0]))
        h_edit.setValidator(QIntValidator(100, 1800))
        h_edit.setPlaceholderText("输入高度值")
        height_row_layout.addWidget(h_edit)
        
        layout.addWidget(height_row)
        
        # 宽度输入行
        width_row = QWidget()
        width_row_layout = QHBoxLayout(width_row)
        width_row_layout.setContentsMargins(0, 0, 0, 0)
        width_row_layout.setSpacing(12)
        
        width_label = QLabel("📌 宽度" + (":" if mode == 'custom_px' else " (mm)："))
        width_label.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-weight: bold;
            font-size: 14px;
        """)
        width_label.setFixedWidth(100)
        width_row_layout.addWidget(width_label)
        
        w_edit = QLineEdit(str(self.custom_size[1]))
        w_edit.setValidator(QIntValidator(100, 1800))
        w_edit.setPlaceholderText("输入宽度值")
        width_row_layout.addWidget(w_edit)
        
        layout.addWidget(width_row)
        
        layout.addSpacing(8)
        
        # 按钮行（减小上边距）
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 6, 0, 0)
        button_layout.setSpacing(12)
        
        button_style = """
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                color: white;
                font-size: 14px;
                font-weight: bold;
                min-width: 90px;
                min-height: 38px;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
        """
        
        cancel_style = """
            QPushButton {
                background-color: hsl(0, 0%, 30%);
                border: none;
                border-radius: 6px;
                padding: 10px 28px;
                color: white;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: hsl(0, 0%, 40%);
            }
            QPushButton:pressed {
                background-color: hsl(0, 0%, 25%);
            }
        """
        
        # 取消按钮
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.setStyleSheet(cancel_style)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        
        # 确定按钮
        confirm_btn = QPushButton("✅ 确定")
        confirm_btn.setStyleSheet(button_style)
        
        def confirm():
            try:
                h, w = int(h_edit.text()), int(w_edit.text())
                if w > h or h < 100 or w < 100 or h > 1800 or w > 1800:
                    QMessageBox.warning(dialog, "错误", "尺寸不符合要求！\n\n请确保：\n1. 宽度 ≤ 高度\n2. 尺寸在 100-1800 范围内")
                    return
                if mode == 'custom_mm':
                    h, w = int(h * 300 / 25.4), int(w * 300 / 25.4)
                self.custom_size = (h, w)
                dialog.accept()
            except:
                QMessageBox.warning(dialog, "错误", "请输入有效的数值！")
        
        confirm_btn.clicked.connect(confirm)
        button_layout.addWidget(confirm_btn)
        
        layout.addWidget(button_row)
        dialog.exec()
    
    def _show_advanced_dialog(self):
        """显示高级参数对话框官方）"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QWidget
        from PyQt6.QtCore import Qt
        
        dialog = QDialog()
        dialog.setWindowTitle("高级裁剪参数")
        dialog.setMinimumWidth(550)
        dialog.setStyleSheet("QDialog { background-color: hsl(222.2, 84%, 4.9%); color: hsl(213, 31%, 91%); }")
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题说明
        title = QLabel("⚡ 智能裁剪算法参数")
        title.setStyleSheet("""
            color: hsl(221.2, 83.2%, 53.3%);
            font-size: 15px;
            font-weight: bold;
            padding-bottom: 4px;
        """)
        layout.addWidget(title)
        
        # 总体说明
        info = QLabel(
            "💡 这些参数用于控制证件照的裁剪效果，默认值已经很好，仅当需要微调时才需调整。"
        )
        info.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            background-color: hsl(217.2, 32.6%, 17.5%);
            border-radius: 4px;
            padding: 10px;
            font-size: 12px;
            line-height: 1.6;
        """)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        slider_style = """
            QSlider::groove:horizontal {
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                height: 8px;
                background: hsl(224, 71.4%, 4.1%);
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: hsl(221.2, 83.2%, 53.3%);
                border: none;
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: hsl(221.2, 83.2%, 60%);
            }
            QSlider::sub-page:horizontal {
                background: hsl(221.2, 83.2%, 53.3%);
                border-radius: 4px;
            }
        """
        
        label_style = "color: hsl(213, 31%, 91%); font-size: 13px; font-weight: bold;"
        desc_style = "color: hsl(215, 20.2%, 65.1%); font-size: 11px; padding-left: 20px; padding-top: 4px; line-height: 1.6;"
        
        # 参数1：人脸面积占比
        ratio_container = QWidget()
        ratio_layout = QVBoxLayout(ratio_container)
        ratio_layout.setContentsMargins(0, 0, 0, 0)
        ratio_layout.setSpacing(4)
        
        ratio_label = QLabel(f"🔍 人脸面积占比：{self.advanced_params['head_measure_ratio']:.2f}")
        ratio_label.setStyleSheet(label_style)
        ratio_layout.addWidget(ratio_label)
        
        ratio_desc = QLabel(
            "💡 控制人脸在照片中的大小。较小值(0.15)适合半身照，默认值(0.20)适合大多数场景，较大值(0.25)适合特写照。"
        )
        ratio_desc.setStyleSheet(desc_style)
        ratio_desc.setWordWrap(True)
        ratio_layout.addWidget(ratio_desc)
        
        ratio_slider = QSlider(Qt.Orientation.Horizontal)
        ratio_slider.setRange(15, 25)  # 0.15 - 0.25
        ratio_slider.setValue(int(self.advanced_params['head_measure_ratio'] * 100))
        ratio_slider.setStyleSheet(slider_style)
        ratio_slider.valueChanged.connect(lambda v: ratio_label.setText(f"🔍 人脸面积占比：{v/100:.2f}"))
        ratio_layout.addWidget(ratio_slider)
        
        layout.addWidget(ratio_container)
        
        # 参数2：头顶距离上边界
        distance_container = QWidget()
        distance_layout = QVBoxLayout(distance_container)
        distance_layout.setContentsMargins(0, 0, 0, 0)
        distance_layout.setSpacing(4)
        
        distance_label = QLabel(f"📏 头顶距离上边界：{self.advanced_params['top_distance_max']:.2f}")
        distance_label.setStyleSheet(label_style)
        distance_layout.addWidget(distance_label)
        
        distance_desc = QLabel(
            "💡 控制头顶到照片上边缘的距离。较小值(0.10)照片更紧凑，默认值(0.12)符合证件照规范，较大值(0.15)照片更宽松。"
        )
        distance_desc.setStyleSheet(desc_style)
        distance_desc.setWordWrap(True)
        distance_layout.addWidget(distance_desc)
        
        distance_slider = QSlider(Qt.Orientation.Horizontal)
        distance_slider.setRange(10, 15)  # 0.10 - 0.15
        distance_slider.setValue(int(self.advanced_params['top_distance_max'] * 100))
        distance_slider.setStyleSheet(slider_style)
        distance_slider.valueChanged.connect(lambda v: distance_label.setText(f"📏 头顶距离上边界：{v/100:.2f}"))
        distance_layout.addWidget(distance_slider)
        
        layout.addWidget(distance_container)
        
        # 按钮行
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 12, 0, 0)
        button_layout.setSpacing(10)
        
        button_style = """
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
            QPushButton:pressed {
                background-color: hsl(221.2, 83.2%, 45%);
            }
        """
        
        reset_button_style = """
            QPushButton {
                background-color: hsl(224, 71.4%, 4.1%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
        """
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置")
        reset_btn.setStyleSheet(reset_button_style)
        def reset_values():
            ratio_slider.setValue(20)  # 0.20
            distance_slider.setValue(12)  # 0.12
        reset_btn.clicked.connect(reset_values)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # 确定按钮
        confirm_btn = QPushButton("✅ 确定")
        confirm_btn.setStyleSheet(button_style)
        confirm_btn.clicked.connect(lambda: [
            self.advanced_params.update({
                'head_measure_ratio': ratio_slider.value()/100, 
                'top_distance_max': distance_slider.value()/100
            }),
            dialog.accept()
        ])
        button_layout.addWidget(confirm_btn)
        
        layout.addWidget(button_row)
        dialog.exec()
    
    def _show_beauty_dialog(self):
        """显示美颜设置对话框"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QWidget, QCheckBox
        from PyQt6.QtCore import Qt
        
        dialog = QDialog()
        dialog.setWindowTitle("美颜设置")
        dialog.setMinimumWidth(560)
        dialog.setMinimumHeight(520)
        dialog.setStyleSheet("""
            QDialog {
                background-color: hsl(222.2, 84%, 4.9%);
                color: hsl(213, 31%, 91%);
            }
            QCheckBox {
                color: hsl(213, 31%, 91%);
                font-size: 14px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 3px;
                border: 2px solid hsl(217.2, 32.6%, 17.5%);
                background-color: hsl(224, 71.4%, 4.1%);
            }
            QCheckBox::indicator:checked {
                border: 2px solid hsl(221.2, 83.2%, 53.3%);
                background-color: hsl(221.2, 83.2%, 53.3%);
            }
            QCheckBox::indicator:hover {
                border-color: hsl(221.2, 83.2%, 60%);
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)
        
        slider_style = """
            QSlider::groove:horizontal {
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                height: 6px;
                background: hsl(224, 71.4%, 4.1%);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: hsl(221.2, 83.2%, 53.3%);
                border: none;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: hsl(221.2, 83.2%, 60%);
            }
            QSlider::sub-page:horizontal {
                background: hsl(221.2, 83.2%, 53.3%);
                border-radius: 3px;
            }
        """
        
        label_style = "color: hsl(215, 20.2%, 65.1%); font-size: 14px; font-weight: bold;"
        value_label_style = "color: hsl(213, 31%, 91%); font-size: 14px; font-weight: bold;"
        
        # 启用美颜开关
        enable_row = QWidget()
        enable_row_layout = QHBoxLayout(enable_row)
        enable_row_layout.setContentsMargins(0, 0, 0, 0)
        enable_row_layout.setSpacing(12)
        
        enable_check = QCheckBox("✨ 启用美颜")
        enable_check.setChecked(self.beauty_params.get('enabled', False))
        enable_check.setStyleSheet("font-size: 15px; font-weight: bold; color: hsl(221.2, 83.2%, 53.3%);")
        enable_row_layout.addWidget(enable_check)
        enable_row_layout.addStretch()
        
        layout.addWidget(enable_row)
        
        # 设置说明
        info_label = QLabel("💡 说明：美颜功能可以优化皮肤色调、调整亮度对比度、增强锐度，让证件照更加美观。建议适度调整，避免过度修饰。")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            color: hsl(38, 92%, 50%);
            background-color: hsla(38, 92%, 50%, 0.1);
            border: 1px solid hsla(38, 92%, 50%, 0.3);
            border-radius: 6px;
            padding: 10px;
            font-size: 12px;
        """)
        layout.addWidget(info_label)
        
        # 美白滑块 (0-15)
        whitening_row = QWidget()
        whitening_layout = QHBoxLayout(whitening_row)
        whitening_layout.setContentsMargins(0, 0, 0, 0)
        whitening_label = QLabel("🌟 美白:")
        whitening_label.setStyleSheet(label_style)
        whitening_label.setFixedWidth(100)
        whitening_layout.addWidget(whitening_label)
        
        whitening_slider = QSlider(Qt.Orientation.Horizontal)
        whitening_slider.setRange(0, 15)
        whitening_slider.setValue(self.beauty_params['whitening'])
        whitening_slider.setStyleSheet(slider_style)
        whitening_layout.addWidget(whitening_slider)
        
        whitening_value = QLabel(str(self.beauty_params['whitening']))
        whitening_value.setStyleSheet(value_label_style)
        whitening_value.setFixedWidth(50)
        whitening_value.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        whitening_layout.addWidget(whitening_value)
        whitening_slider.valueChanged.connect(lambda v: whitening_value.setText(str(v)))
        layout.addWidget(whitening_row)
        
        # 亮度滑块 (-5 ~ +25)
        brightness_row = QWidget()
        brightness_layout = QHBoxLayout(brightness_row)
        brightness_layout.setContentsMargins(0, 0, 0, 0)
        brightness_label = QLabel("☀️ 亮度:")
        brightness_label.setStyleSheet(label_style)
        brightness_label.setFixedWidth(100)
        brightness_layout.addWidget(brightness_label)
        
        brightness_slider = QSlider(Qt.Orientation.Horizontal)
        brightness_slider.setRange(-5, 25)
        brightness_slider.setValue(self.beauty_params['brightness'])
        brightness_slider.setStyleSheet(slider_style)
        brightness_layout.addWidget(brightness_slider)
        
        brightness_value = QLabel(str(self.beauty_params['brightness']))
        brightness_value.setStyleSheet(value_label_style)
        brightness_value.setFixedWidth(50)
        brightness_value.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        brightness_layout.addWidget(brightness_value)
        brightness_slider.valueChanged.connect(lambda v: brightness_value.setText(str(v)))
        layout.addWidget(brightness_row)
        
        # 对比度滑块 (-10 ~ +50)
        contrast_row = QWidget()
        contrast_layout = QHBoxLayout(contrast_row)
        contrast_layout.setContentsMargins(0, 0, 0, 0)
        contrast_label = QLabel("🎨 对比度:")
        contrast_label.setStyleSheet(label_style)
        contrast_label.setFixedWidth(100)
        contrast_layout.addWidget(contrast_label)
        
        contrast_slider = QSlider(Qt.Orientation.Horizontal)
        contrast_slider.setRange(-10, 50)
        contrast_slider.setValue(self.beauty_params['contrast'])
        contrast_slider.setStyleSheet(slider_style)
        contrast_layout.addWidget(contrast_slider)
        
        contrast_value = QLabel(str(self.beauty_params['contrast']))
        contrast_value.setStyleSheet(value_label_style)
        contrast_value.setFixedWidth(50)
        contrast_value.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        contrast_layout.addWidget(contrast_value)
        contrast_slider.valueChanged.connect(lambda v: contrast_value.setText(str(v)))
        layout.addWidget(contrast_row)
        
        # 饱和度滑块 (-10 ~ +50)
        saturation_row = QWidget()
        saturation_layout = QHBoxLayout(saturation_row)
        saturation_layout.setContentsMargins(0, 0, 0, 0)
        saturation_label = QLabel("🌈 饱和度:")
        saturation_label.setStyleSheet(label_style)
        saturation_label.setFixedWidth(100)
        saturation_layout.addWidget(saturation_label)
        
        saturation_slider = QSlider(Qt.Orientation.Horizontal)
        saturation_slider.setRange(-10, 50)
        saturation_slider.setValue(self.beauty_params['saturation'])
        saturation_slider.setStyleSheet(slider_style)
        saturation_layout.addWidget(saturation_slider)
        
        saturation_value = QLabel(str(self.beauty_params['saturation']))
        saturation_value.setStyleSheet(value_label_style)
        saturation_value.setFixedWidth(50)
        saturation_value.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        saturation_layout.addWidget(saturation_value)
        saturation_slider.valueChanged.connect(lambda v: saturation_value.setText(str(v)))
        layout.addWidget(saturation_row)
        
        # 锐化滑块 (0-5)
        sharpen_row = QWidget()
        sharpen_layout = QHBoxLayout(sharpen_row)
        sharpen_layout.setContentsMargins(0, 0, 0, 0)
        sharpen_label = QLabel("✨ 锐化:")
        sharpen_label.setStyleSheet(label_style)
        sharpen_label.setFixedWidth(100)
        sharpen_layout.addWidget(sharpen_label)
        
        sharpen_slider = QSlider(Qt.Orientation.Horizontal)
        sharpen_slider.setRange(0, 5)
        sharpen_slider.setValue(self.beauty_params['sharpen'])
        sharpen_slider.setStyleSheet(slider_style)
        sharpen_layout.addWidget(sharpen_slider)
        
        sharpen_value = QLabel(str(self.beauty_params['sharpen']))
        sharpen_value.setStyleSheet(value_label_style)
        sharpen_value.setFixedWidth(50)
        sharpen_value.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        sharpen_layout.addWidget(sharpen_value)
        sharpen_slider.valueChanged.connect(lambda v: sharpen_value.setText(str(v)))
        layout.addWidget(sharpen_row)
        
        # 按钮行
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 8, 0, 0)
        button_layout.setSpacing(12)
        
        button_style = """
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                color: white;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
            QPushButton:pressed {
                background-color: hsl(221.2, 83.2%, 45%);
            }
        """
        
        reset_btn = QPushButton("🔄 重置")
        reset_btn.setStyleSheet(button_style.replace("hsl(221.2, 83.2%, 53.3%)", "hsl(0, 0%, 45%)").replace("hsl(221.2, 83.2%, 60%)", "hsl(0, 0%, 55%)").replace("hsl(221.2, 83.2%, 45%)", "hsl(0, 0%, 40%)"))
        
        def reset_settings():
            enable_check.setChecked(False)
            whitening_slider.setValue(0)
            brightness_slider.setValue(0)
            contrast_slider.setValue(0)
            saturation_slider.setValue(0)
            sharpen_slider.setValue(0)
        
        reset_btn.clicked.connect(reset_settings)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        confirm_btn = QPushButton("✅ 确定")
        confirm_btn.setStyleSheet(button_style)
        
        def save_settings():
            self.beauty_params.update({
                'enabled': enable_check.isChecked(),
                'whitening': whitening_slider.value(),
                'brightness': brightness_slider.value(),
                'contrast': contrast_slider.value(),
                'saturation': saturation_slider.value(),
                'sharpen': sharpen_slider.value()
            })
            dialog.accept()
        
        confirm_btn.clicked.connect(save_settings)
        button_layout.addWidget(confirm_btn)
        
        layout.addWidget(button_row)
        
        # 显示对话框
        dialog.exec()
    
    def _show_plugin_dialog(self):
        """显示插件功能对话框"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QCheckBox
        
        dialog = QDialog()
        dialog.setWindowTitle("插件功能")
        dialog.setMinimumWidth(520)
        dialog.setStyleSheet("QDialog { background-color: hsl(222.2, 84%, 4.9%); color: hsl(213, 31%, 91%); }")
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题说明
        title = QLabel("⚡ 插件功能设置")
        title.setStyleSheet("""
            color: hsl(221.2, 83.2%, 53.3%);
            font-size: 15px;
            font-weight: bold;
            padding-bottom: 4px;
        """)
        layout.addWidget(title)
        
        # 功能说明框
        desc_box = QLabel(
            "💡 高级功能选项，默认设置已经很好，仅在需要时启用。启用后会在生成证件照时应用相应处理。"
        )
        desc_box.setStyleSheet("""
            background-color: hsl(217.2, 32.6%, 17.5%);
            border-radius: 4px;
            padding: 10px;
            color: hsl(215, 20.2%, 65.1%);
            font-size: 12px;
            line-height: 1.6;
        """)
        desc_box.setWordWrap(True)
        layout.addWidget(desc_box)
        
        checkbox_style = """
            QCheckBox {
                color: hsl(213, 31%, 91%);
                font-size: 14px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 4px;
                background-color: hsl(224, 71.4%, 4.1%);
            }
            QCheckBox::indicator:hover {
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
            QCheckBox::indicator:checked {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
        """
        
        # 插件1：人脸旋转对齐
        face_align_check = QCheckBox("🎯 人脸旋转对齐")
        face_align_check.setChecked(self.plugin_params['face_alignment'])
        face_align_check.setStyleSheet(checkbox_style)
        layout.addWidget(face_align_check)
        
        face_align_desc = QLabel(
            "💡 自动检测并旋转人脸，使人脸水平对齐，适用场景：拍照时头部有轻微偏转。"
        )
        face_align_desc.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-size: 11px;
            padding-left: 28px;
            padding-bottom: 6px;
            line-height: 1.6;
        """)
        face_align_desc.setWordWrap(True)
        layout.addWidget(face_align_desc)
        
        # 插件2：水平翻转
        h_flip_check = QCheckBox("🔄 水平翻转")
        h_flip_check.setChecked(self.plugin_params['horizontal_flip'])
        h_flip_check.setStyleSheet(checkbox_style)
        layout.addWidget(h_flip_check)
        
        h_flip_desc = QLabel(
            "💡 将图片水平翻转（镜像），适用场景：需要镜像效果的证件照。"
        )
        h_flip_desc.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-size: 11px;
            padding-left: 28px;
            padding-bottom: 6px;
            line-height: 1.6;
        """)
        h_flip_desc.setWordWrap(True)
        layout.addWidget(h_flip_desc)
        
        # 插件3：JPEG格式输出
        jpeg_check = QCheckBox("💾 JPEG格式输出")
        jpeg_check.setChecked(self.plugin_params['jpeg_format'])
        jpeg_check.setStyleSheet(checkbox_style)
        layout.addWidget(jpeg_check)
        
        jpeg_desc = QLabel(
            "💡 使用JPEG格式保存（默认PNG），优点：文件更小，上传速度更快；缺点：JPEG不支持透明背景。"
        )
        jpeg_desc.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-size: 11px;
            padding-left: 28px;
            padding-bottom: 6px;
            line-height: 1.6;
        """)
        jpeg_desc.setWordWrap(True)
        layout.addWidget(jpeg_desc)
        
        # 按钮行
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 12, 0, 0)
        button_layout.setSpacing(10)
        
        button_style = """
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
            QPushButton:pressed {
                background-color: hsl(221.2, 83.2%, 45%);
            }
        """
        
        reset_button_style = """
            QPushButton {
                background-color: hsl(224, 71.4%, 4.1%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
        """
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置")
        reset_btn.setStyleSheet(reset_button_style)
        def reset_values():
            face_align_check.setChecked(False)
            h_flip_check.setChecked(False)
            jpeg_check.setChecked(False)
        reset_btn.clicked.connect(reset_values)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # 确定按钮
        confirm_btn = QPushButton("✅ 确定")
        confirm_btn.setStyleSheet(button_style)
        confirm_btn.clicked.connect(lambda: [
            self.plugin_params.update({
                'face_alignment': face_align_check.isChecked(),
                'horizontal_flip': h_flip_check.isChecked(),
                'jpeg_format': jpeg_check.isChecked(),
            }),
            dialog.accept()
        ])
        button_layout.addWidget(confirm_btn)
        
        layout.addWidget(button_row)
        dialog.exec()
    
    def set_fit_button_visible(self, visible: bool):
        """由预览控件调用：图片大于显示区时显示“适应框/实际大小”按钮"""
        if hasattr(self, 'fit_actual_btn'):
            self.fit_actual_btn.setVisible(visible)
    
    def update_fit_button_text(self, fit: bool):
        """更新按钮文字：显示点击后将切换到的状态。当前适应框→显示“实际大小”，当前实际大小→显示“适应框”"""
        if hasattr(self, 'fit_actual_btn'):
            self.fit_actual_btn.setText("实际大小" if fit else "适应框")
    
    def _on_fit_actual_clicked(self):
        """切换预览：适应框 ↔ 实际大小（通过模块保存的 tab 引用）"""
        try:
            tab = getattr(self, '_tab_ref', None)
            if tab and hasattr(tab, 'preview_widget') and hasattr(tab.preview_widget, 'toggle_fit_actual'):
                tab.preview_widget.toggle_fit_actual()
        except Exception:
            pass
    
    def _show_output_type_dialog(self):
        """显示输出类型对话框"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QRadioButton, QButtonGroup
        
        dialog = QDialog()
        dialog.setWindowTitle("输出类型")
        dialog.setMinimumWidth(520)
        dialog.setStyleSheet("QDialog { background-color: hsl(222.2, 84%, 4.9%); color: hsl(213, 31%, 91%); }")
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题说明
        title = QLabel("⚡ 输出照片类型")
        title.setStyleSheet("""
            color: hsl(221.2, 83.2%, 53.3%);
            font-size: 15px;
            font-weight: bold;
            padding-bottom: 4px;
        """)
        layout.addWidget(title)
        
        # 功能说明框
        desc_box = QLabel(
            "💡 选择合适的输出类型，默认输出标准照，透明照适用于后期处理、高清照适用于打印。"
        )
        desc_box.setStyleSheet("""
            background-color: hsl(217.2, 32.6%, 17.5%);
            border-radius: 4px;
            padding: 10px;
            color: hsl(215, 20.2%, 65.1%);
            font-size: 12px;
            line-height: 1.6;
        """)
        desc_box.setWordWrap(True)
        layout.addWidget(desc_box)
        
        radio_style = """
            QRadioButton {
                color: hsl(213, 31%, 91%);
                font-size: 13px;
                spacing: 6px;
                padding: 6px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 9px;
                background-color: hsl(224, 71.4%, 4.1%);
            }
            QRadioButton::indicator:hover {
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
            QRadioButton::indicator:checked {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
        """
        
        # 创建单选按钮组
        type_group = QButtonGroup()
        
        # 选项1：标准照
        standard_radio = QRadioButton("📷 标准照（默认）")
        standard_radio.setChecked(self.output_types['standard_photo'])
        standard_radio.setStyleSheet(radio_style)
        type_group.addButton(standard_radio, 0)
        layout.addWidget(standard_radio)
        
        standard_desc = QLabel(
            "💡 说明：标准分辨率证件照，适用于大多数场景。<br>"
            "· 分辨率：根据尺寸需求（如一寸295x413px）<br>"
            "· 格式：PNG/JPEG（带背景色）"
        )
        standard_desc.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-size: 12px;
            padding-left: 32px;
            padding-bottom: 8px;
            line-height: 1.8;
        """)
        standard_desc.setWordWrap(True)
        layout.addWidget(standard_desc)
        
        # 选项2：高清照
        hd_radio = QRadioButton("🌟 高清照（HD Photo）")
        hd_radio.setChecked(self.output_types['hd_photo'])
        hd_radio.setStyleSheet(radio_style)
        type_group.addButton(hd_radio, 1)
        layout.addWidget(hd_radio)
        
        hd_desc = QLabel(
            "💡 说明：2倍分辨率高清照，适用于打印和高质量要求。<br>"
            "· 分辨率：标准尺寸的2倍（如一寸590x826px）<br>"
            "· 格式：PNG/JPEG（带背景色）"
        )
        hd_desc.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-size: 12px;
            padding-left: 32px;
            padding-bottom: 8px;
            line-height: 1.8;
        """)
        hd_desc.setWordWrap(True)
        layout.addWidget(hd_desc)
        
        # 选项3：透明标准照
        matting_standard_radio = QRadioButton("🔳 透明标准照")
        matting_standard_radio.setChecked(self.output_types['matting_standard'])
        matting_standard_radio.setStyleSheet(radio_style)
        type_group.addButton(matting_standard_radio, 2)
        layout.addWidget(matting_standard_radio)
        
        matting_standard_desc = QLabel(
            "💡 说明：透明背景PNG格式，适用于后期处理。<br>"
            "· 分辨率：标准尺寸<br>"
            "· 格式：PNG（透明通道）"
        )
        matting_standard_desc.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-size: 12px;
            padding-left: 32px;
            padding-bottom: 8px;
            line-height: 1.8;
        """)
        matting_standard_desc.setWordWrap(True)
        layout.addWidget(matting_standard_desc)
        
        # 选项4：透明高清照
        matting_hd_radio = QRadioButton("✨ 透明高清照")
        matting_hd_radio.setChecked(self.output_types['matting_hd'])
        matting_hd_radio.setStyleSheet(radio_style)
        type_group.addButton(matting_hd_radio, 3)
        layout.addWidget(matting_hd_radio)
        
        matting_hd_desc = QLabel(
            "💡 说明：2倍分辨率透明背景，高质量后期处理。<br>"
            "· 分辨率：标准尺寸的2倍<br>"
            "· 格式：PNG（透明通道）"
        )
        matting_hd_desc.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-size: 12px;
            padding-left: 32px;
            padding-bottom: 8px;
            line-height: 1.8;
        """)
        matting_hd_desc.setWordWrap(True)
        layout.addWidget(matting_hd_desc)
        
        # 选项5：排版照
        layout_photo_radio = QRadioButton("🖼️ 排版照")
        layout_photo_radio.setChecked(self.output_types['layout_photo'])
        layout_photo_radio.setStyleSheet(radio_style)
        type_group.addButton(layout_photo_radio, 4)
        layout.addWidget(layout_photo_radio)
        
        layout_photo_desc = QLabel(
            "💡 说明：智能排版在相纸上，便于打印。<br>"
            "· 功能：根据相纸大小智能排列多张照片<br>"
            "· 需要：在 '🖨️ 打印排版' 中选择相纸大小"
        )
        layout_photo_desc.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-size: 12px;
            padding-left: 32px;
            padding-bottom: 8px;
            line-height: 1.8;
        """)
        layout_photo_desc.setWordWrap(True)
        layout.addWidget(layout_photo_desc)
        
        # 按钮行
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 16, 0, 0)
        button_layout.setSpacing(12)
        
        button_style = """
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
            QPushButton:pressed {
                background-color: hsl(221.2, 83.2%, 45%);
            }
        """
        
        reset_button_style = """
            QPushButton {
                background-color: hsl(224, 71.4%, 4.1%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
        """
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置默认值")
        reset_btn.setStyleSheet(reset_button_style)
        def reset_values():
            standard_radio.setChecked(True)
        reset_btn.clicked.connect(reset_values)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # 确定按钮
        confirm_btn = QPushButton("✅ 确定应用")
        confirm_btn.setStyleSheet(button_style)
        def apply_output_type():
            # 根据选择更新output_types
            selected_id = type_group.checkedId()
            self.output_types = {
                'standard_photo': selected_id == 0,
                'hd_photo': selected_id == 1,
                'matting_standard': selected_id == 2,
                'matting_hd': selected_id == 3,
                'layout_photo': selected_id == 4,
            }
            dialog.accept()
        confirm_btn.clicked.connect(apply_output_type)
        button_layout.addWidget(confirm_btn)
        
        layout.addWidget(button_row)
        dialog.exec()
    
    def _show_print_layout_dialog(self):
        """显示打印排版对话框（官方）"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QComboBox, QCheckBox
        
        dialog = QDialog()
        dialog.setWindowTitle("打印排版设置")
        dialog.setMinimumWidth(550)
        dialog.setStyleSheet("QDialog { background-color: hsl(222.2, 84%, 4.9%); color: hsl(213, 31%, 91%); }")
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)
        
        # 标题说明
        title = QLabel("⚙️ 打印排版设置")
        title.setStyleSheet("""
            color: hsl(221.2, 83.2%, 53.3%);
            font-size: 16px;
            font-weight: bold;
            padding-bottom: 8px;
        """)
        layout.addWidget(title)
        
        # 启用排版复选框
        enable_check = QCheckBox("📎 启用打印排版")
        enable_check.setChecked(self.print_params['enabled'])
        enable_check.setStyleSheet("""
            QCheckBox {
                color: hsl(213, 31%, 91%);
                font-size: 14px;
                font-weight: bold;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 4px;
                background-color: hsl(224, 71.4%, 4.1%);
            }
            QCheckBox::indicator:hover {
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
            QCheckBox::indicator:checked {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
        """)
        layout.addWidget(enable_check)
        
        # 相纸选择
        paper_row = QWidget()
        paper_layout = QHBoxLayout(paper_row)
        paper_layout.setContentsMargins(0, 12, 0, 0)
        
        paper_label = QLabel("📜 相纸选择:")
        paper_label.setStyleSheet("color: hsl(213, 31%, 91%); font-size: 14px; font-weight: bold;")
        paper_label.setFixedWidth(100)
        paper_layout.addWidget(paper_label)
        
        from ui.custom_widgets import StyledComboBox
        
        paper_combo = StyledComboBox()
        paper_combo.addItems(list(self.paper_sizes.keys()))
        paper_combo.setCurrentText(self.print_params['paper_size'])
        paper_combo.setMinimumWidth(200)
        # 使用与主界面一致的样式
        combo_style = """
            QComboBox {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 8px 12px;
                padding-right: 30px;
                color: hsl(213, 31%, 91%);
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
            QComboBox::drop-down {
                border: none;
                border-left: 1px solid hsl(217.2, 32.6%, 17.5%);
                background: hsl(217.2, 32.6%, 17.5%);
                width: 25px;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                selection-background-color: hsl(221.2, 83.2%, 53.3%);
                selection-color: white;
                color: hsl(213, 31%, 91%);
            }
        """
        paper_combo.setStyleSheet(combo_style)
        paper_layout.addWidget(paper_combo)
        layout.addWidget(paper_row)
        
        # 相纸尺寸说明
        paper_info = QLabel(
            "📊 <b>相纸尺寸说明</b><br>"
            "· 六寸: 1205x1795px （最常用）<br>"
            "· 五寸: 1051x1500px<br>"
            "· A4: 2479x3508px<br>"
            "· 3R: 1051x1500px<br>"
            "· 4R: 1205x1795px"
        )
        paper_info.setStyleSheet("""
            color: hsl(215, 20.2%, 65.1%);
            font-size: 12px;
            padding: 12px;
            background-color: hsl(217.2, 32.6%, 17.5%);
            border-radius: 6px;
            line-height: 1.8;
        """)
        paper_info.setWordWrap(True)
        layout.addWidget(paper_info)
        
        # 按钮行
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 16, 0, 0)
        button_layout.setSpacing(12)
        
        button_style = """
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
            QPushButton:pressed {
                background-color: hsl(221.2, 83.2%, 45%);
            }
        """
        
        reset_button_style = """
            QPushButton {
                background-color: hsl(224, 71.4%, 4.1%);
                color: hsl(213, 31%, 91%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: hsl(217.2, 32.6%, 17.5%);
                border-color: hsl(221.2, 83.2%, 53.3%);
            }
        """
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置默认值")
        reset_btn.setStyleSheet(reset_button_style)
        def reset_values():
            enable_check.setChecked(False)
            paper_combo.setCurrentText('六寸')
        reset_btn.clicked.connect(reset_values)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # 确定按钮
        confirm_btn = QPushButton("✅ 确定应用")
        confirm_btn.setStyleSheet(button_style)
        confirm_btn.clicked.connect(lambda: [
            self.print_params.update({
                'enabled': enable_check.isChecked(),
                'paper_size': paper_combo.currentText(),
            }),
            dialog.accept()
        ])
        button_layout.addWidget(confirm_btn)
        
        layout.addWidget(button_row)
        dialog.exec()
    
    def _show_watermark_dialog(self):
        """显示水印设置对话框"""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                      QSlider, QPushButton, QWidget, QRadioButton, 
                                      QButtonGroup, QLineEdit, QFileDialog, QCheckBox, QColorDialog)
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor
        from ui.custom_widgets import StyledComboBox
        
        dialog = QDialog()
        dialog.setWindowTitle("水印设置")
        dialog.setMinimumWidth(520)
        dialog.setStyleSheet("""
            QDialog {
                background-color: hsl(222.2, 84%, 4.9%);
                color: hsl(213, 31%, 91%);
            }
            QRadioButton {
                color: hsl(213, 31%, 91%);
                font-size: 13px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid hsl(217.2, 32.6%, 17.5%);
                background-color: hsl(224, 71.4%, 4.1%);
            }
            QRadioButton::indicator:checked {
                border: 2px solid hsl(221.2, 83.2%, 53.3%);
                background-color: hsl(221.2, 83.2%, 53.3%);
            }
            QRadioButton::indicator:hover {
                border-color: hsl(221.2, 83.2%, 60%);
            }
            QLineEdit {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 4px;
                padding: 6px;
                color: hsl(213, 31%, 91%);
                font-size: 13px;
            }
            QCheckBox {
                color: hsl(213, 31%, 91%);
                font-size: 14px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 3px;
                border: 2px solid hsl(217.2, 32.6%, 17.5%);
                background-color: hsl(224, 71.4%, 4.1%);
            }
            QCheckBox::indicator:checked {
                border: 2px solid hsl(221.2, 83.2%, 53.3%);
                background-color: hsl(221.2, 83.2%, 53.3%);
            }
            QCheckBox::indicator:hover {
                border-color: hsl(221.2, 83.2%, 60%);
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(4)
        layout.setContentsMargins(20, 12, 20, 12)
        
        slider_style = """
            QSlider::groove:horizontal {
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                height: 6px;
                background: hsl(224, 71.4%, 4.1%);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: hsl(221.2, 83.2%, 53.3%);
                border: none;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: hsl(221.2, 83.2%, 60%);
            }
            QSlider::sub-page:horizontal {
                background: hsl(221.2, 83.2%, 53.3%);
                border-radius: 3px;
            }
        """
        
        label_style = "color: hsl(213, 31%, 91%); font-size: 14px; font-weight: bold;"
        value_style = "color: hsl(221.2, 83.2%, 53.3%); font-size: 14px; font-weight: bold;"
        
        # 启用水印开关
        enable_row = QWidget()
        enable_row_layout = QHBoxLayout(enable_row)
        enable_row_layout.setContentsMargins(0, 0, 0, 0)
        enable_row_layout.setSpacing(12)
        
        enable_check = QCheckBox("💧 启用水印")
        enable_check.setChecked(self.watermark_params.get('enabled', False))
        enable_check.setStyleSheet("font-size: 15px; font-weight: bold; color: hsl(221.2, 83.2%, 53.3%);")
        enable_row_layout.addWidget(enable_check)
        enable_row_layout.addStretch()
        
        layout.addWidget(enable_row)
        
        # 水印类型
        type_row = QWidget()
        type_row_layout = QHBoxLayout(type_row)
        type_row_layout.setContentsMargins(0, 0, 0, 0)
        type_row_layout.setSpacing(12)
        
        type_label = QLabel("💧 水印类型:")
        type_label.setStyleSheet(label_style)
        type_row_layout.addWidget(type_label)
        
        type_group = QButtonGroup()
        type_text_radio = QRadioButton("文本水印")
        type_image_radio = QRadioButton("图片水印")
        type_group.addButton(type_text_radio)
        type_group.addButton(type_image_radio)
        
        current_type = self.watermark_params.get('type', 'text')
        if current_type == 'text':
            type_text_radio.setChecked(True)
        else:
            type_image_radio.setChecked(True)
        
        type_row_layout.addWidget(type_text_radio)
        type_row_layout.addWidget(type_image_radio)
        type_row_layout.addStretch()
        
        layout.addWidget(type_row)
        
        # 文本水印参数
        text_params_widget = QWidget()
        text_params_layout = QVBoxLayout(text_params_widget)
        text_params_layout.setContentsMargins(0, 0, 0, 0)
        text_params_layout.setSpacing(6)
        
        # 文本内容
        text_row = QWidget()
        text_row_layout = QHBoxLayout(text_row)
        text_row_layout.setContentsMargins(0, 0, 0, 0)
        text_label = QLabel("💬 文本内容:")
        text_label.setStyleSheet(label_style)
        text_label.setFixedWidth(120)
        text_row_layout.addWidget(text_label)
        
        self.text_input = QLineEdit()
        self.text_input.setText(self.watermark_params.get('text', ''))
        self.text_input.setPlaceholderText("请输入水印文字")
        self.text_input.setMinimumHeight(32)
        self.text_input.setStyleSheet("background-color: hsl(224, 71.4%, 4.1%); border: 1px solid hsl(217.2, 32.6%, 17.5%); border-radius: 6px; padding: 6px 8px; color: hsl(213, 31%, 91%); font-size: 13px;")
        text_row_layout.addWidget(self.text_input)
        text_params_layout.addWidget(text_row)
        
        # 字体选择
        font_family_row = QWidget()
        font_family_row_layout = QHBoxLayout(font_family_row)
        font_family_row_layout.setContentsMargins(0, 0, 0, 0)
        font_family_label = QLabel("🆎 字体:")
        font_family_label.setStyleSheet(label_style)
        font_family_label.setFixedWidth(120)
        font_family_row_layout.addWidget(font_family_label)
        
        font_combo = StyledComboBox()
        font_combo.addItems(['微软雅黑', '黑体', '楷体', '宋体', 'Arial', 'Times New Roman'])
        current_font = self.watermark_params.get('font_family', '微软雅黑')
        font_combo.setCurrentText(current_font)
        font_combo.setMinimumHeight(32)
        font_combo.setStyleSheet("""
            QComboBox {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                padding: 6px;
                padding-right: 30px;
                color: hsl(213, 31%, 91%);
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: hsl(215, 20.2%, 65.1%);
            }
            QComboBox::drop-down {
                border: none;
                border-left: 1px solid hsl(217.2, 32.6%, 17.5%);
                background: hsl(217.2, 32.6%, 17.5%);
                width: 25px;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QComboBox::drop-down:hover {
                background: hsl(221.2, 83.2%, 53.3%);
            }
            QComboBox QAbstractItemView {
                background-color: hsl(224, 71.4%, 4.1%);
                border: 1px solid hsl(217.2, 32.6%, 17.5%);
                border-radius: 6px;
                selection-background-color: hsl(221.2, 83.2%, 53.3%);
                selection-color: white;
                color: hsl(213, 31%, 91%);
                padding: 4px;
            }
        """)
        font_family_row_layout.addWidget(font_combo)
        text_params_layout.addWidget(font_family_row)
        
        # 字体大小
        font_row = QWidget()
        font_row_layout = QHBoxLayout(font_row)
        font_row_layout.setContentsMargins(0, 0, 0, 0)
        font_label = QLabel("📏 字体大小:")
        font_label.setStyleSheet(label_style)
        font_label.setFixedWidth(120)
        font_row_layout.addWidget(font_label)
        
        font_slider = QSlider(Qt.Orientation.Horizontal)
        font_slider.setMinimum(10)
        font_slider.setMaximum(100)
        font_slider.setValue(self.watermark_params.get('font_size', 20))
        font_slider.setStyleSheet(slider_style)
        font_row_layout.addWidget(font_slider)
        
        font_value = QLabel(str(font_slider.value()))
        font_value.setStyleSheet(value_style)
        font_value.setFixedWidth(40)
        font_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        font_row_layout.addWidget(font_value)
        font_row_layout.setSpacing(8)
        font_slider.valueChanged.connect(lambda v: font_value.setText(str(v)))
        text_params_layout.addWidget(font_row)
        
        # 字体颜色
        color_row = QWidget()
        color_row_layout = QHBoxLayout(color_row)
        color_row_layout.setContentsMargins(0, 0, 0, 0)
        color_label = QLabel("🎨 字体颜色:")
        color_label.setStyleSheet(label_style)
        color_label.setFixedWidth(120)
        color_row_layout.addWidget(color_label)
        
        # 颜色显示框
        color_display = QWidget()
        color_display.setFixedSize(100, 32)
        current_font_color = self.watermark_params.get('color', '#FFFFFF')
        color_display.setStyleSheet(f"background-color: {current_font_color}; border: 1px solid hsl(217.2, 32.6%, 17.5%); border-radius: 6px;")
        color_row_layout.addWidget(color_display)
        
        # 选择颜色按钮
        def choose_font_color():
            color_dialog = QColorDialog(dialog)
            color_dialog.setWindowTitle("选择字体颜色")
            color_dialog.setCurrentColor(QColor(current_font_color))
            # 设置中文界面
            color_dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
            
            # 美化样式
            color_dialog.setStyleSheet("""
                QColorDialog {
                    background-color: hsl(222.2, 84%, 4.9%);
                    color: hsl(213, 31%, 91%);
                }
                QLabel {
                    color: hsl(213, 31%, 91%);
                    font-size: 13px;
                }
                QPushButton {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                    color: hsl(213, 31%, 91%);
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 500;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: hsl(221.2, 83.2%, 53.3%);
                    border-color: hsl(221.2, 83.2%, 53.3%);
                }
                QSpinBox, QLineEdit {
                    background-color: hsl(224, 71.4%, 4.1%);
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    border-radius: 4px;
                    padding: 6px;
                    color: hsl(213, 31%, 91%);
                }
                QSpinBox:focus, QLineEdit:focus {
                    border-color: hsl(221.2, 83.2%, 53.3%);
                }
            """)
            color_dialog.setStandardColor(0, QColor(current_font_color).rgb())
            
            # 翻译为中文
            translate_color_dialog_to_chinese(color_dialog)
            
            if color_dialog.exec() == QDialog.DialogCode.Accepted:
                color = color_dialog.currentColor()
                if color.isValid():
                    hex_color = color.name()
                    color_display.setStyleSheet(f"background-color: {hex_color}; border: 1px solid hsl(217.2, 32.6%, 17.5%); border-radius: 6px;")
                    color_display.setProperty('selected_color', hex_color)
        
        color_btn = QPushButton("🎫 选择颜色")
        color_btn.setMinimumHeight(32)
        color_btn.setStyleSheet("""
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
        """)
        color_btn.clicked.connect(choose_font_color)
        color_row_layout.addWidget(color_btn)
        color_row_layout.addStretch()
        
        # 初始化颜色属性
        color_display.setProperty('selected_color', current_font_color)
        
        text_params_layout.addWidget(color_row)
        
        # 透明度 (文字水印)
        text_opacity_row = QWidget()
        text_opacity_row_layout = QHBoxLayout(text_opacity_row)
        text_opacity_row_layout.setContentsMargins(0, 0, 0, 0)
        text_opacity_label = QLabel("👁️ 透明度:")
        text_opacity_label.setStyleSheet(label_style)
        text_opacity_label.setFixedWidth(120)
        text_opacity_row_layout.addWidget(text_opacity_label)
        
        text_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        text_opacity_slider.setMinimum(0)
        text_opacity_slider.setMaximum(100)
        text_opacity_slider.setValue(int(self.watermark_params.get('opacity', 100) * 100) if self.watermark_params.get('opacity', 100) <= 1 else int(self.watermark_params.get('opacity', 100)))
        text_opacity_slider.setStyleSheet(slider_style)
        text_opacity_row_layout.addWidget(text_opacity_slider)
        
        text_opacity_value = QLabel(str(text_opacity_slider.value()))
        text_opacity_value.setStyleSheet(value_style)
        text_opacity_value.setFixedWidth(40)
        text_opacity_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        text_opacity_row_layout.addWidget(text_opacity_value)
        text_opacity_row_layout.setSpacing(8)
        text_opacity_slider.valueChanged.connect(lambda v: text_opacity_value.setText(str(v)))
        text_params_layout.addWidget(text_opacity_row)
        
        # 位置 (文字水印)
        text_position_row = QWidget()
        text_position_row_layout = QHBoxLayout(text_position_row)
        text_position_row_layout.setContentsMargins(0, 0, 0, 0)
        text_position_label = QLabel("📍 位置:")
        text_position_label.setStyleSheet(label_style)
        text_position_label.setFixedWidth(120)
        text_position_row_layout.addWidget(text_position_label)
        
        text_position_group = QButtonGroup()
        text_position_top_left_radio = QRadioButton("左上")
        text_position_top_right_radio = QRadioButton("右上")
        text_position_bottom_left_radio = QRadioButton("左下")
        text_position_bottom_right_radio = QRadioButton("右下")
        text_position_tiled_radio = QRadioButton("平铺")
        text_position_group.addButton(text_position_top_left_radio)
        text_position_group.addButton(text_position_top_right_radio)
        text_position_group.addButton(text_position_bottom_left_radio)
        text_position_group.addButton(text_position_bottom_right_radio)
        text_position_group.addButton(text_position_tiled_radio)
        
        # 获取当前位置，确保有默认值
        current_position = self.watermark_params.get('position', 'bottom_right')
        if current_position == 'top_left':
            text_position_top_left_radio.setChecked(True)
        elif current_position == 'top_right':
            text_position_top_right_radio.setChecked(True)
        elif current_position == 'bottom_left':
            text_position_bottom_left_radio.setChecked(True)
        elif current_position == 'tiled':
            text_position_tiled_radio.setChecked(True)
        elif current_position == 'bottom_right':
            text_position_bottom_right_radio.setChecked(True)
        else:
            # 默认选中右下角
            text_position_bottom_right_radio.setChecked(True)
        
        text_position_row_layout.addWidget(text_position_top_left_radio)
        text_position_row_layout.addWidget(text_position_top_right_radio)
        text_position_row_layout.addWidget(text_position_bottom_left_radio)
        text_position_row_layout.addWidget(text_position_bottom_right_radio)
        text_position_row_layout.addWidget(text_position_tiled_radio)
        text_params_layout.addWidget(text_position_row)
        
        layout.addWidget(text_params_widget)
        
        # 图片水印参数
        image_params_widget = QWidget()
        image_params_layout = QVBoxLayout(image_params_widget)
        image_params_layout.setContentsMargins(0, 0, 0, 0)
        image_params_layout.setSpacing(6)
        
        # 图片路径
        path_row = QWidget()
        path_row_layout = QHBoxLayout(path_row)
        path_row_layout.setContentsMargins(0, 0, 0, 0)
        path_label = QLabel("🖼️ 图片路径:")
        path_label.setStyleSheet(label_style)
        path_label.setFixedWidth(120)
        path_row_layout.addWidget(path_label)
        
        self.path_input = QLineEdit()
        self.path_input.setText(self.watermark_params.get('image_path', '') or '')
        self.path_input.setPlaceholderText("选择水印图片")
        self.path_input.setMinimumHeight(32)
        self.path_input.setStyleSheet("background-color: hsl(224, 71.4%, 4.1%); border: 1px solid hsl(217.2, 32.6%, 17.5%); border-radius: 6px; padding: 6px 8px; color: hsl(213, 31%, 91%); font-size: 13px;")
        path_row_layout.addWidget(self.path_input)
        image_params_layout.addWidget(path_row)
        
        # 选择图片按钮
        select_btn = QPushButton("📁 选择图片")
        select_btn.setMinimumHeight(32)
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
        """)
        
        def select_watermark_image():
            from PyQt6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(
                dialog, "选择水印图片", "", 
                "Image Files (*.png *.jpg *.jpeg *.bmp)"
            )
            if file_path:
                self.path_input.setText(file_path)
        
        select_btn.clicked.connect(select_watermark_image)
        image_params_layout.addWidget(select_btn)
        
        # 透明度 (图片水印)
        image_opacity_row = QWidget()
        image_opacity_row_layout = QHBoxLayout(image_opacity_row)
        image_opacity_row_layout.setContentsMargins(0, 0, 0, 0)
        image_opacity_label = QLabel("👁️ 透明度:")
        image_opacity_label.setStyleSheet(label_style)
        image_opacity_label.setFixedWidth(120)
        image_opacity_row_layout.addWidget(image_opacity_label)
        
        image_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        image_opacity_slider.setMinimum(0)
        image_opacity_slider.setMaximum(100)
        image_opacity_slider.setValue(int(self.watermark_params.get('opacity', 100) * 100) if self.watermark_params.get('opacity', 100) <= 1 else int(self.watermark_params.get('opacity', 100)))
        image_opacity_slider.setStyleSheet(slider_style)
        image_opacity_row_layout.addWidget(image_opacity_slider)
        
        image_opacity_value = QLabel(str(image_opacity_slider.value()))
        image_opacity_value.setStyleSheet(value_style)
        image_opacity_value.setFixedWidth(40)
        image_opacity_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        image_opacity_row_layout.addWidget(image_opacity_value)
        image_opacity_row_layout.setSpacing(8)
        image_opacity_slider.valueChanged.connect(lambda v: image_opacity_value.setText(str(v)))
        image_params_layout.addWidget(image_opacity_row)
        
        # 大小 (图片水印)
        image_size_row = QWidget()
        image_size_row_layout = QHBoxLayout(image_size_row)
        image_size_row_layout.setContentsMargins(0, 0, 0, 0)
        image_size_label = QLabel("📐 大小:")
        image_size_label.setStyleSheet(label_style)
        image_size_label.setFixedWidth(120)
        image_size_row_layout.addWidget(image_size_label)
        
        image_size_slider = QSlider(Qt.Orientation.Horizontal)
        image_size_slider.setMinimum(10)
        image_size_slider.setMaximum(200)
        # 从image_scale读取，转换为百分比
        current_scale = self.watermark_params.get('image_scale', 0.1)
        image_size_slider.setValue(int(current_scale * 100) if current_scale <= 2 else int(current_scale))
        image_size_slider.setStyleSheet(slider_style)
        image_size_row_layout.addWidget(image_size_slider)
        
        image_size_value = QLabel(str(image_size_slider.value()))
        image_size_value.setStyleSheet(value_style)
        image_size_value.setFixedWidth(40)
        image_size_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        image_size_row_layout.addWidget(image_size_value)
        image_size_row_layout.setSpacing(8)
        image_size_slider.valueChanged.connect(lambda v: image_size_value.setText(str(v)))
        image_params_layout.addWidget(image_size_row)
        
        # 位置 (图片水印)
        image_position_row = QWidget()
        image_position_row_layout = QHBoxLayout(image_position_row)
        image_position_row_layout.setContentsMargins(0, 0, 0, 0)
        image_position_label = QLabel("📍 位置:")
        image_position_label.setStyleSheet(label_style)
        image_position_label.setFixedWidth(120)
        image_position_row_layout.addWidget(image_position_label)
        
        image_position_group = QButtonGroup()
        image_position_top_left_radio = QRadioButton("左上")
        image_position_top_right_radio = QRadioButton("右上")
        image_position_bottom_left_radio = QRadioButton("左下")
        image_position_bottom_right_radio = QRadioButton("右下")
        image_position_tiled_radio = QRadioButton("平铺")
        image_position_group.addButton(image_position_top_left_radio)
        image_position_group.addButton(image_position_top_right_radio)
        image_position_group.addButton(image_position_bottom_left_radio)
        image_position_group.addButton(image_position_bottom_right_radio)
        image_position_group.addButton(image_position_tiled_radio)
        
        # 获取当前位置，确保有默认值
        current_position = self.watermark_params.get('position', 'bottom_right')
        if current_position == 'top_left':
            image_position_top_left_radio.setChecked(True)
        elif current_position == 'top_right':
            image_position_top_right_radio.setChecked(True)
        elif current_position == 'bottom_left':
            image_position_bottom_left_radio.setChecked(True)
        elif current_position == 'tiled':
            image_position_tiled_radio.setChecked(True)
        elif current_position == 'bottom_right':
            image_position_bottom_right_radio.setChecked(True)
        else:
            # 默认选中右下角
            image_position_bottom_right_radio.setChecked(True)
        
        image_position_row_layout.addWidget(image_position_top_left_radio)
        image_position_row_layout.addWidget(image_position_top_right_radio)
        image_position_row_layout.addWidget(image_position_bottom_left_radio)
        image_position_row_layout.addWidget(image_position_bottom_right_radio)
        image_position_row_layout.addWidget(image_position_tiled_radio)
        image_params_layout.addWidget(image_position_row)
        
        layout.addWidget(image_params_widget)
        
        # 控制显示/隐藏
        def toggle_watermark_type():
            is_text = type_text_radio.isChecked()
            text_params_widget.setVisible(is_text)
            image_params_widget.setVisible(not is_text)
            # 调整窗口大小以适应内容
            dialog.adjustSize()
        
        type_text_radio.toggled.connect(toggle_watermark_type)
        type_image_radio.toggled.connect(toggle_watermark_type)
        toggle_watermark_type()
        
        # 按钮行
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(12)
        
        button_style = """
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 6px;
                padding: 6px 20px;
                color: white;
                font-size: 13px;
                font-weight: bold;
                min-width: 80px;
                min-height: 32px;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
        """
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置")
        reset_btn.setStyleSheet(button_style.replace("hsl(221.2, 83.2%, 53.3%)", "hsl(0, 0%, 45%)").replace("hsl(221.2, 83.2%, 60%)", "hsl(0, 0%, 55%)"))
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # 确定按钮
        confirm_btn = QPushButton("✅ 确定")
        confirm_btn.setStyleSheet(button_style)
        button_layout.addWidget(confirm_btn)
        
        layout.addWidget(button_row)
        
        # 重置按钮功能
        def reset_settings():
            enable_check.setChecked(False)
            type_text_radio.setChecked(True)
            self.text_input.setText('')
            font_slider.setValue(20)
            color_display.setStyleSheet(f"background-color: #FFFFFF; border: 1px solid hsl(217.2, 32.6%, 17.5%); border-radius: 6px;")
            color_display.setProperty('selected_color', '#FFFFFF')
            text_opacity_slider.setValue(100)
            text_position_bottom_right_radio.setChecked(True)
            self.path_input.setText('')
            image_opacity_slider.setValue(100)
            image_size_slider.setValue(10)
            image_position_bottom_right_radio.setChecked(True)
        
        reset_btn.clicked.connect(reset_settings)
        
        # 确定按钮功能
        def save_watermark_settings():
            # 检查：如果启用水印且选择了图片水印，必须选择水印图片
            if enable_check.isChecked() and type_image_radio.isChecked():
                image_path = self.path_input.text().strip()
                if not image_path:
                    from ui.custom_widgets import StyledMessageBox
                    StyledMessageBox.warning(dialog, "提示", "请选择水印图片")
                    return
                if not os.path.exists(image_path):
                    from ui.custom_widgets import StyledMessageBox
                    StyledMessageBox.warning(dialog, "提示", f"水印图片不存在：{image_path}")
                    return
            
            is_text = type_text_radio.isChecked()
            # 根据类型获取对应的透明度和位置
            if is_text:
                opacity_val = text_opacity_slider.value() / 100.0  # 转换为0-1
                if text_position_top_left_radio.isChecked():
                    pos = 'top_left'
                elif text_position_top_right_radio.isChecked():
                    pos = 'top_right'
                elif text_position_bottom_left_radio.isChecked():
                    pos = 'bottom_left'
                elif text_position_tiled_radio.isChecked():
                    pos = 'tiled'
                else:
                    pos = 'bottom_right'
                # 获取选中的颜色
                selected_color = color_display.property('selected_color') or current_font_color
            else:
                opacity_val = image_opacity_slider.value() / 100.0  # 转换为0-1
                if image_position_top_left_radio.isChecked():
                    pos = 'top_left'
                elif image_position_top_right_radio.isChecked():
                    pos = 'top_right'
                elif image_position_bottom_left_radio.isChecked():
                    pos = 'bottom_left'
                elif image_position_tiled_radio.isChecked():
                    pos = 'tiled'
                else:
                    pos = 'bottom_right'
                selected_color = '#FFFFFF'  # 图片水印不需要颜色
            
            self.watermark_params.update({
                'enabled': enable_check.isChecked(),
                'type': 'text' if is_text else 'image',
                'text': self.text_input.text(),
                'font_family': font_combo.currentText(),
                'size': font_slider.value(),  # 修正：使用'size'不是'font_size'
                'color': selected_color,  # 修正：使用'color'不是'font_color'
                'opacity': opacity_val,
                'position': pos,
                'image_path': self.path_input.text(),
                'image_scale': image_size_slider.value() / 100.0,  # 转换为0-2的小数
            })
            dialog.accept()
        
        confirm_btn.clicked.connect(save_watermark_settings)
        
        dialog.exec()
    
    def _show_output_dialog(self):
        """
        显示输出设置对话框（KB大小 + DPI）
        完全按照 HivisionIDPhotos 官方实现
        """
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
            QCheckBox, QSlider, QRadioButton, QButtonGroup
        )
        from PyQt6.QtCore import Qt
        
        dialog = QDialog()
        dialog.setWindowTitle("输出设置")
        dialog.setMinimumWidth(500)
        dialog.setStyleSheet("""
            QDialog {
                background-color: hsl(222.2, 84%, 4.9%);
                color: hsl(213, 31%, 91%);
            }
            QCheckBox, QRadioButton {
                color: hsl(213, 31%, 91%);
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid hsl(217.2, 32.6%, 17.5%);
                background-color: hsl(224, 71.4%, 4.1%);
            }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                border: 2px solid hsl(221.2, 83.2%, 53.3%);
                background-color: hsl(221.2, 83.2%, 53.3%);
            }
            QCheckBox::indicator:hover, QRadioButton::indicator:hover {
                border-color: hsl(221.2, 83.2%, 60%);
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        slider_style = """
            QSlider::groove:horizontal {
                height: 4px;
                background: hsl(217.2, 32.6%, 17.5%);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: hsl(221.2, 83.2%, 53.3%);
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: hsl(221.2, 83.2%, 60%);
            }
        """
        
        label_style = "color: hsl(213, 31%, 91%); font-size: 13px; font-weight: bold;"
        value_style = "color: hsl(221.2, 83.2%, 53.3%); font-size: 13px; font-weight: bold;"
        
        # 启用KB大小控制
        kb_enable_check = QCheckBox("📊 启用KB大小控制")
        kb_enable_check.setChecked(self.output_params.get('kb_enabled', False))
        kb_enable_check.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(kb_enable_check)
        
        # KB参数区域
        kb_params_widget = QWidget()
        kb_params_layout = QVBoxLayout(kb_params_widget)
        kb_params_layout.setContentsMargins(0, 0, 0, 0)
        kb_params_layout.setSpacing(8)
        
        # 目标KB大小
        kb_row = QWidget()
        kb_row_layout = QHBoxLayout(kb_row)
        kb_row_layout.setContentsMargins(0, 0, 0, 0)
        kb_label = QLabel("🎯 目标大小:")
        kb_label.setStyleSheet(label_style)
        kb_label.setFixedWidth(100)
        kb_row_layout.addWidget(kb_label)
        
        kb_slider = QSlider(Qt.Orientation.Horizontal)
        kb_slider.setMinimum(30)
        kb_slider.setMaximum(200)
        kb_slider.setValue(self.output_params.get('target_kb', 50))
        kb_slider.setStyleSheet(slider_style)
        kb_row_layout.addWidget(kb_slider)
        
        kb_value = QLabel(f"{kb_slider.value()} KB")
        kb_value.setStyleSheet(value_style)
        kb_value.setFixedWidth(80)
        kb_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        kb_row_layout.addWidget(kb_value)
        kb_slider.valueChanged.connect(lambda v: kb_value.setText(f"{v} KB"))
        kb_params_layout.addWidget(kb_row)
        
        # KB模式
        mode_label = QLabel("🔧 压缩模式:")
        mode_label.setStyleSheet(label_style)
        kb_params_layout.addWidget(mode_label)
        
        mode_group = QButtonGroup()
        mode_max_radio = QRadioButton("不大于目标大小")
        mode_exact_radio = QRadioButton("精确等于目标大小（填充空字节)")
        mode_group.addButton(mode_max_radio)
        mode_group.addButton(mode_exact_radio)
        
        current_mode = self.output_params.get('kb_mode', 'max')
        if current_mode == 'max':
            mode_max_radio.setChecked(True)
        else:
            mode_exact_radio.setChecked(True)
        
        kb_params_layout.addWidget(mode_max_radio)
        kb_params_layout.addWidget(mode_exact_radio)
        
        layout.addWidget(kb_params_widget)
        
        # 分隔线
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: hsl(217.2, 32.6%, 17.5%);")
        layout.addWidget(separator)
        
        # 启用DPI设置
        dpi_enable_check = QCheckBox("🖨️ 启用DPI设置（打印清晰度）")
        dpi_enable_check.setChecked(self.output_params.get('dpi_enabled', False))
        dpi_enable_check.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(dpi_enable_check)
        
        # DPI参数区域
        dpi_params_widget = QWidget()
        dpi_params_layout = QVBoxLayout(dpi_params_widget)
        dpi_params_layout.setContentsMargins(0, 0, 0, 0)
        dpi_params_layout.setSpacing(8)
        
        # DPI选择
        dpi_group = QButtonGroup()
        dpi_300_radio = QRadioButton("300 DPI（标准打印）")
        dpi_600_radio = QRadioButton("600 DPI（高质量打印）")
        dpi_group.addButton(dpi_300_radio)
        dpi_group.addButton(dpi_600_radio)
        
        current_dpi = self.output_params.get('dpi', 300)
        if current_dpi == 300:
            dpi_300_radio.setChecked(True)
        else:
            dpi_600_radio.setChecked(True)
        
        dpi_params_layout.addWidget(dpi_300_radio)
        dpi_params_layout.addWidget(dpi_600_radio)
        
        layout.addWidget(dpi_params_widget)
        
        # 控制启用状态
        def toggle_kb_enable():
            kb_params_widget.setEnabled(kb_enable_check.isChecked())
        
        def toggle_dpi_enable():
            dpi_params_widget.setEnabled(dpi_enable_check.isChecked())
        
        kb_enable_check.toggled.connect(toggle_kb_enable)
        dpi_enable_check.toggled.connect(toggle_dpi_enable)
        toggle_kb_enable()
        toggle_dpi_enable()
        
        layout.addStretch()
        
        # 按钮行
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        button_style = """
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 4px;
                padding: 8px 24px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
        """
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置")
        reset_btn.setStyleSheet(button_style.replace("hsl(221.2, 83.2%, 53.3%)", "hsl(0, 0%, 45%)").replace("hsl(221.2, 83.2%, 60%)", "hsl(0, 0%, 55%)"))
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # 确定按钮
        confirm_btn = QPushButton("✅ 确定")
        confirm_btn.setStyleSheet(button_style)
        button_layout.addWidget(confirm_btn)
        
        layout.addWidget(button_row)
        
        # 重置按钮功能
        reset_btn.clicked.connect(lambda: [
            kb_enable_check.setChecked(False),
            kb_slider.setValue(50),
            mode_max_radio.setChecked(True),
            dpi_enable_check.setChecked(False),
            dpi_300_radio.setChecked(True),
        ])
        
        # 确定按钮功能
        confirm_btn.clicked.connect(lambda: [
            self.output_params.update({
                'kb_enabled': kb_enable_check.isChecked(),
                'target_kb': kb_slider.value(),
                'kb_mode': 'max' if mode_max_radio.isChecked() else 'exact',
                'dpi_enabled': dpi_enable_check.isChecked(),
                'dpi': 300 if dpi_300_radio.isChecked() else 600,
            }),
            dialog.accept()
        ])
        
        dialog.exec()
    
    def _apply_watermark(self, img_rgba: np.ndarray) -> np.ndarray:
        
        label_style = "color: hsl(215, 20.2%, 65.1%); font-size: 13px;"
        value_label_style = "color: hsl(213, 31%, 91%); font-size: 13px; font-weight: bold;"
        
        # 启用水印复选框
        enable_check = QCheckBox("启用水印")
        enable_check.setChecked(self.watermark_params.get('enabled', False))
        enable_check.setStyleSheet("font-size: 14px; font-weight: bold; color: hsl(221.2, 83.2%, 53.3%);")
        layout.addWidget(enable_check)
        
        # 水印类型选择
        type_row = QWidget()
        type_layout = QHBoxLayout(type_row)
        type_layout.setContentsMargins(0, 0, 0, 0)
        type_label = QLabel("水印类型:")
        type_label.setStyleSheet(label_style)
        type_layout.addWidget(type_label)
        
        type_group = QButtonGroup(dialog)
        text_radio = QRadioButton("文字水印")
        image_radio = QRadioButton("图片水印")
        type_group.addButton(text_radio)
        type_group.addButton(image_radio)
        
        if self.watermark_params.get('type', 'text') == 'text':
            text_radio.setChecked(True)
        else:
            image_radio.setChecked(True)
        
        type_layout.addWidget(text_radio)
        type_layout.addWidget(image_radio)
        type_layout.addStretch()
        layout.addWidget(type_row)
        
        # 创建一个堆叠容器，用于切换文字和图片参数
        from PyQt6.QtWidgets import QStackedWidget
        params_stack = QStackedWidget()
        
        # === 文字水印参数 ===
        text_params_widget = QWidget()
        text_params_layout = QVBoxLayout(text_params_widget)
        text_params_layout.setContentsMargins(0, 0, 0, 0)
        text_params_layout.setSpacing(8)  # 减小间距
        
        # 水印文字
        text_row = QWidget()
        text_row_layout = QHBoxLayout(text_row)
        text_row_layout.setContentsMargins(0, 0, 0, 0)
        text_label = QLabel("📝 水印文字:")
        text_label.setStyleSheet(label_style)
        text_label.setFixedWidth(100)
        text_row_layout.addWidget(text_label)
        
        text_edit = QLineEdit(self.watermark_params.get('text', 'HivisionIDPhoto'))
        text_edit.setPlaceholderText("请输入水印文字")
        text_row_layout.addWidget(text_edit)
        text_params_layout.addWidget(text_row)
        
        # 字体大小 (10-100)
        size_row = QWidget()
        size_layout = QHBoxLayout(size_row)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_label = QLabel("🔤 字体大小:")
        size_label.setStyleSheet(label_style)
        size_label.setFixedWidth(100)
        size_layout.addWidget(size_label)
        
        size_slider = QSlider(Qt.Orientation.Horizontal)
        size_slider.setRange(10, 100)
        size_slider.setValue(self.watermark_params.get('size', 20))
        size_slider.setStyleSheet(slider_style)
        size_layout.addWidget(size_slider)
        
        size_value = QLabel(str(self.watermark_params.get('size', 20)))
        size_value.setStyleSheet(value_label_style)
        size_value.setFixedWidth(40)
        size_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        size_layout.addWidget(size_value)
        size_layout.setSpacing(8)
        size_slider.valueChanged.connect(lambda v: size_value.setText(str(v)))
        text_params_layout.addWidget(size_row)
        
        # 透明度 (0-1)
        opacity_row = QWidget()
        opacity_layout = QHBoxLayout(opacity_row)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_label = QLabel("🔆 透明度:")
        opacity_label.setStyleSheet(label_style)
        opacity_label.setFixedWidth(100)
        opacity_layout.addWidget(opacity_label)
        
        opacity_slider = QSlider(Qt.Orientation.Horizontal)
        opacity_slider.setRange(0, 100)
        opacity_slider.setValue(int(self.watermark_params.get('opacity', 0.15) * 100))
        opacity_slider.setStyleSheet(slider_style)
        opacity_layout.addWidget(opacity_slider)
        
        opacity_value = QLabel(f"{self.watermark_params.get('opacity', 0.15):.2f}")
        opacity_value.setStyleSheet(value_label_style)
        opacity_value.setFixedWidth(40)
        opacity_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        opacity_layout.addWidget(opacity_value)
        opacity_layout.setSpacing(8)
        opacity_slider.valueChanged.connect(lambda v: opacity_value.setText(f"{v/100:.2f}"))
        text_params_layout.addWidget(opacity_row)
        
        # 角度 (0-360)
        angle_row = QWidget()
        angle_layout = QHBoxLayout(angle_row)
        angle_layout.setContentsMargins(0, 0, 0, 0)
        angle_label = QLabel("🔄 角度:")
        angle_label.setStyleSheet(label_style)
        angle_label.setFixedWidth(100)
        angle_layout.addWidget(angle_label)
        
        angle_slider = QSlider(Qt.Orientation.Horizontal)
        angle_slider.setRange(0, 360)
        angle_slider.setValue(self.watermark_params.get('angle', 30))
        angle_slider.setStyleSheet(slider_style)
        angle_layout.addWidget(angle_slider)
        
        angle_value = QLabel(str(self.watermark_params.get('angle', 30)))
        angle_value.setStyleSheet(value_label_style)
        angle_value.setFixedWidth(40)
        angle_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        angle_layout.addWidget(angle_value)
        angle_layout.setSpacing(8)
        angle_slider.valueChanged.connect(lambda v: angle_value.setText(str(v)))
        text_params_layout.addWidget(angle_row)
        
        # 间距 (10-200)
        space_row = QWidget()
        space_layout = QHBoxLayout(space_row)
        space_layout.setContentsMargins(0, 0, 0, 0)
        space_label = QLabel("📏 间距:")
        space_label.setStyleSheet(label_style)
        space_label.setFixedWidth(100)
        space_layout.addWidget(space_label)
        
        space_slider = QSlider(Qt.Orientation.Horizontal)
        space_slider.setRange(10, 200)
        space_slider.setValue(self.watermark_params.get('space', 25))
        space_slider.setStyleSheet(slider_style)
        space_layout.addWidget(space_slider)
        
        space_value = QLabel(str(self.watermark_params.get('space', 25)))
        space_value.setStyleSheet(value_label_style)
        space_value.setFixedWidth(40)
        space_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        space_layout.addWidget(space_value)
        space_layout.setSpacing(8)
        space_slider.valueChanged.connect(lambda v: space_value.setText(str(v)))
        text_params_layout.addWidget(space_row)
        
        # 颜色
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_label = QLabel("🎨 颜色:")
        color_label.setStyleSheet(label_style)
        color_label.setFixedWidth(100)
        color_layout.addWidget(color_label)
        
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor
        
        color_display = QWidget()
        color_display.setFixedSize(100, 30)
        current_color = self.watermark_params.get('color', '#8B8B1B')
        color_display.setStyleSheet(f"background-color: {current_color}; border: 1px solid hsl(217.2, 32.6%, 17.5%); border-radius: 4px;")
        color_layout.addWidget(color_display)
        
        def choose_color():
            color_dialog = QColorDialog(dialog)
            color_dialog.setWindowTitle("选择水印颜色")
            color_dialog.setCurrentColor(QColor(current_color))
            # 设置中文界面
            color_dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
            
            # 美化样式
            color_dialog.setStyleSheet("""
                QColorDialog {
                    background-color: hsl(222.2, 84%, 4.9%);
                    color: hsl(213, 31%, 91%);
                }
                QLabel {
                    color: hsl(213, 31%, 91%);
                    font-size: 13px;
                }
                QPushButton {
                    background-color: hsl(217.2, 32.6%, 17.5%);
                    color: hsl(213, 31%, 91%);
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 500;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: hsl(221.2, 83.2%, 53.3%);
                    border-color: hsl(221.2, 83.2%, 53.3%);
                }
                QSpinBox, QLineEdit {
                    background-color: hsl(224, 71.4%, 4.1%);
                    border: 1px solid hsl(217.2, 32.6%, 17.5%);
                    border-radius: 4px;
                    padding: 6px;
                    color: hsl(213, 31%, 91%);
                }
                QSpinBox:focus, QLineEdit:focus {
                    border-color: hsl(221.2, 83.2%, 53.3%);
                }
            """)
            
            # 翻译为中文
            translate_color_dialog_to_chinese(color_dialog)
            
            if color_dialog.exec() == QDialog.DialogCode.Accepted:
                color = color_dialog.currentColor()
                if color.isValid():
                    hex_color = color.name()
                    color_display.setStyleSheet(f"background-color: {hex_color}; border: 1px solid hsl(217.2, 32.6%, 17.5%); border-radius: 4px;")
                    # 保存到临时变量
                    color_display.setProperty('color', hex_color)
        
        color_btn = QPushButton("选择颜色")
        color_btn.setStyleSheet("""
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
        """)
        color_btn.clicked.connect(choose_color)
        color_layout.addWidget(color_btn)
        color_layout.addStretch()
        text_params_layout.addWidget(color_row)
        
        # 添加到堆叠容器
        params_stack.addWidget(text_params_widget)
        
        # === 图片水印参数 ===
        image_params_widget = QWidget()
        image_params_layout = QVBoxLayout(image_params_widget)
        image_params_layout.setContentsMargins(0, 0, 0, 0)
        image_params_layout.setSpacing(8)  # 减小间距
        
        # 水印图片路径
        image_path_row = QWidget()
        image_path_layout = QHBoxLayout(image_path_row)
        image_path_layout.setContentsMargins(0, 0, 0, 0)
        image_path_label = QLabel("🖼️ 水印图片:")
        image_path_label.setStyleSheet(label_style)
        image_path_label.setFixedWidth(100)
        image_path_layout.addWidget(image_path_label)
        
        image_path_edit = QLineEdit(self.watermark_params.get('image_path', '') or '')
        image_path_edit.setPlaceholderText("选择水印图片")
        image_path_layout.addWidget(image_path_edit)
        
        browse_btn = QPushButton("浏览")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
        """)
        
        def browse_image():
            file_path, _ = QFileDialog.getOpenFileName(
                dialog, "选择水印图片", "", 
                "Image Files (*.png *.jpg *.jpeg *.bmp)"
            )
            if file_path:
                image_path_edit.setText(file_path)
        
        browse_btn.clicked.connect(browse_image)
        image_path_layout.addWidget(browse_btn)
        image_params_layout.addWidget(image_path_row)
        
        # 图片透明度
        img_opacity_row = QWidget()
        img_opacity_layout = QHBoxLayout(img_opacity_row)
        img_opacity_layout.setContentsMargins(0, 0, 0, 0)
        img_opacity_label = QLabel("🔆 透明度:")
        img_opacity_label.setStyleSheet(label_style)
        img_opacity_label.setFixedWidth(100)
        img_opacity_layout.addWidget(img_opacity_label)
        
        img_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        img_opacity_slider.setRange(0, 100)
        img_opacity_slider.setValue(int(self.watermark_params.get('image_opacity', 0.3) * 100))
        img_opacity_slider.setStyleSheet(slider_style)
        img_opacity_layout.addWidget(img_opacity_slider)
        
        img_opacity_value = QLabel(f"{self.watermark_params.get('image_opacity', 0.3):.2f}")
        img_opacity_value.setStyleSheet(value_label_style)
        img_opacity_value.setFixedWidth(40)
        img_opacity_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        img_opacity_layout.addWidget(img_opacity_value)
        img_opacity_layout.setSpacing(8)
        img_opacity_slider.valueChanged.connect(lambda v: img_opacity_value.setText(f"{v/100:.2f}"))
        image_params_layout.addWidget(img_opacity_row)
        
        # 图片缩放
        img_scale_row = QWidget()
        img_scale_layout = QHBoxLayout(img_scale_row)
        img_scale_layout.setContentsMargins(0, 0, 0, 0)
        img_scale_label = QLabel("🔍 缩放比例:")
        img_scale_label.setStyleSheet(label_style)
        img_scale_label.setFixedWidth(100)
        img_scale_layout.addWidget(img_scale_label)
        
        img_scale_slider = QSlider(Qt.Orientation.Horizontal)
        img_scale_slider.setRange(5, 50)  # 5%-50%
        img_scale_slider.setValue(int(self.watermark_params.get('image_scale', 0.1) * 100))
        img_scale_slider.setStyleSheet(slider_style)
        img_scale_layout.addWidget(img_scale_slider)
        
        img_scale_value = QLabel(f"{self.watermark_params.get('image_scale', 0.1):.2f}")
        img_scale_value.setStyleSheet(value_label_style)
        img_scale_value.setFixedWidth(40)
        img_scale_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        img_scale_layout.addWidget(img_scale_value)
        img_scale_layout.setSpacing(8)
        img_scale_slider.valueChanged.connect(lambda v: img_scale_value.setText(f"{v/100:.2f}"))
        image_params_layout.addWidget(img_scale_row)
        
        # 去背景色复选框
        img_remove_bg_check = QCheckBox("✨ 去除背景色（使用透明背景）")
        img_remove_bg_check.setChecked(self.watermark_params.get('image_remove_bg', False))
        img_remove_bg_check.setStyleSheet("font-size: 13px; color: hsl(215, 20.2%, 65.1%);")
        image_params_layout.addWidget(img_remove_bg_check)
        
        # 添加到堆叠容器
        params_stack.addWidget(image_params_widget)
        
        # 将堆叠容器添加到主布局
        layout.addWidget(params_stack)
        
        # 根据类型显示/隐藏参数
        def toggle_params():
            if text_radio.isChecked():
                params_stack.setCurrentIndex(0)  # 显示文字水印
            else:
                params_stack.setCurrentIndex(1)  # 显示图片水印
        
        # 根据启用状态控制参数区域
        def toggle_enable():
            enabled = enable_check.isChecked()
            text_radio.setEnabled(enabled)
            image_radio.setEnabled(enabled)
            params_stack.setEnabled(enabled)
        
        enable_check.toggled.connect(toggle_enable)
        text_radio.toggled.connect(toggle_params)
        toggle_enable()  # 初始化状态
        toggle_params()
        
        # 选择图片按钮
        select_btn = QPushButton("📁 选择图片")
        select_btn.setMinimumHeight(36)
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
        """)
        
        # 按钮行
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(10)
        
        button_style = """
            QPushButton {
                background-color: hsl(221.2, 83.2%, 53.3%);
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: hsl(221.2, 83.2%, 60%);
            }
            QPushButton:pressed {
                background-color: hsl(221.2, 83.2%, 45%);
            }
        """
        
        reset_btn = QPushButton("🔄 重置")
        reset_btn.setStyleSheet(button_style)
        reset_btn.clicked.connect(lambda: [
            enable_check.setChecked(False),
            text_radio.setChecked(True),
            text_edit.setText('鲲穹AI'),
            size_slider.setValue(20),
            opacity_slider.setValue(15),
            angle_slider.setValue(30),
            space_slider.setValue(25),
            color_display.setStyleSheet("background-color: #8B8B1B; border: 1px solid hsl(217.2, 32.6%, 17.5%); border-radius: 4px;"),
            color_display.setProperty('color', '#8B8B1B'),
            image_path_edit.setText(''),
            img_opacity_slider.setValue(30),
            img_scale_slider.setValue(10),
            img_remove_bg_check.setChecked(False),
        ])
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        confirm_btn = QPushButton("✅ 确定")
        confirm_btn.setStyleSheet(button_style)
        confirm_btn.clicked.connect(lambda: [
            self.watermark_params.update({
                'enabled': enable_check.isChecked(),
                'type': 'text' if text_radio.isChecked() else 'image',
                'text': text_edit.text(),
                'size': size_slider.value(),
                'opacity': opacity_slider.value() / 100,
                'angle': angle_slider.value(),
                'color': color_display.property('color') or '#8B8B1B',
                'space': space_slider.value(),
                'image_path': image_path_edit.text() or None,
                'image_opacity': img_opacity_slider.value() / 100,
                'image_scale': img_scale_slider.value() / 100,
                'image_remove_bg': img_remove_bg_check.isChecked(),
            }),
            dialog.accept()
        ])
        button_layout.addWidget(confirm_btn)
        
        layout.addWidget(button_row)
        
        # 显示对话框
        dialog.exec()
    
    def _apply_watermark(self, img_rgba: np.ndarray) -> np.ndarray:
        """
        应用水印（完全按照 HivisionIDPhotos 官方实现）
        支持文字水印和图片水印
        参考：hivision/plugin/watermark.py
        
        Args:
            img_rgba: RGBA格式图像
            
        Returns:
            添加水印后的RGBA图像
        """
        watermark_type = self.watermark_params.get('type', 'text')
        
        if watermark_type == 'text':
            return self._apply_text_watermark(img_rgba)
        else:
            return self._apply_image_watermark(img_rgba)
    
    def _apply_text_watermark(self, img_rgba: np.ndarray) -> np.ndarray:
        """
        应用文字水印（使用官方 Watermarker 类）
        """
        from PIL import Image
        import math
        from PIL import ImageFont, ImageDraw, ImageEnhance, ImageChops
        
        # 获取水印参数
        text = self.watermark_params.get('text', 'HivisionIDPhoto')
        size = self.watermark_params.get('size', 20)
        opacity = self.watermark_params.get('opacity', 0.15)
        color = self.watermark_params.get('color', '#8B8B1B')
        position = self.watermark_params.get('position', 'tiled')
        font_family = self.watermark_params.get('font_family', '微软雅黑')
        angle = self.watermark_params.get('angle', 30)
        space = self.watermark_params.get('space', 25)
        
        # 转换为RGB（Watermarker需要RGB）
        if img_rgba.shape[2] == 4:
            b, g, r, a = cv2.split(img_rgba)
            rgb = cv2.merge([r, g, b])  # BGR -> RGB
        else:
            rgb = cv2.cvtColor(img_rgba, cv2.COLOR_BGR2RGB)
            a = None
        
        # 转为PIL Image
        pil_image = Image.fromarray(rgb)
        origin_image = pil_image.convert("RGBA")
        
        # 获取字体文件路径
        try:
            import os
            # 根据字体名称选择字体文件
            font_map = {
                '微软雅黑': 'C:/Windows/Fonts/msyh.ttc',
                '黑体': 'C:/Windows/Fonts/simhei.ttf',
                '楷体': 'C:/Windows/Fonts/simkai.ttf',
                '宋体': 'C:/Windows/Fonts/simsun.ttc',
                'Arial': 'C:/Windows/Fonts/arial.ttf',
                'Times New Roman': 'C:/Windows/Fonts/times.ttf',
            }
            font_path = font_map.get(font_family, 'C:/Windows/Fonts/msyh.ttc')
            if not os.path.exists(font_path):
                # 备用方案
                font_path = 'C:/Windows/Fonts/msyh.ttc'
            if not os.path.exists(font_path):
                font = ImageFont.load_default()
            else:
                font = ImageFont.truetype(font_path, size=size)
        except:
            font = ImageFont.load_default()
        
        # 创建水印图像
        width = len(text) * size
        height = round(size * 1.2)
        watermark_image = Image.new(mode="RGBA", size=(width, height))
        draw_table = ImageDraw.Draw(watermark_image)
        draw_table.text(
            (0, 0),
            text,
            fill=color,
            font=font,
        )
        
        # 裁剪边缘
        bg = Image.new(mode="RGBA", size=watermark_image.size)
        diff = ImageChops.difference(watermark_image, bg)
        bbox = diff.getbbox()
        if bbox:
            watermark_image = watermark_image.crop(bbox)
        
        # 设置透明度
        alpha_wm = watermark_image.split()[3]
        alpha_wm = ImageEnhance.Brightness(alpha_wm).enhance(opacity)
        watermark_image.putalpha(alpha_wm)
        
        # 根据位置应用水印
        if position == 'tiled':
            # 平铺模式（官方实现）
            c = int(math.sqrt(origin_image.size[0] ** 2 + origin_image.size[1] ** 2))
            watermark_mask = Image.new(mode="RGBA", size=(c, c))
            y, idx = 0, 0
            while y < c:
                x = -int((watermark_image.size[0] + space) * 0.5 * idx)
                idx = (idx + 1) % 2
                while x < c:
                    watermark_mask.paste(watermark_image, (x, y))
                    x += watermark_image.size[0] + space
                y += watermark_image.size[1] + space
            
            # 旋转水印
            watermark_mask = watermark_mask.rotate(angle)
            
            # 合成到原图
            origin_image.paste(
                watermark_mask,
                (int((origin_image.size[0] - c) / 2), int((origin_image.size[1] - c) / 2)),
                mask=watermark_mask.split()[3],
            )
        else:
            # 单个水印位置
            margin = 10
            w, h = origin_image.size
            wm_w, wm_h = watermark_image.size
            
            if position == 'top_left':
                paste_x, paste_y = margin, margin
            elif position == 'top_right':
                paste_x, paste_y = w - wm_w - margin, margin
            elif position == 'bottom_left':
                paste_x, paste_y = margin, h - wm_h - margin
            else:  # bottom_right
                paste_x, paste_y = w - wm_w - margin, h - wm_h - margin
            
            origin_image.paste(watermark_image, (paste_x, paste_y), mask=watermark_image.split()[3])
        
        # 转回numpy BGR格式
        result_rgb = np.array(origin_image.convert("RGB"))
        result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
        
        # 恢复alpha通道
        if a is not None:
            result = np.dstack([result_bgr, a])
        else:
            result = result_bgr
        
        return result
    
    def _apply_image_watermark(self, img_rgba: np.ndarray) -> np.ndarray:
        """
        应用图片水印
        """
        image_path = self.watermark_params.get('image_path')
        if not image_path or not os.path.exists(image_path):
            print("[水印] 图片水印路径无效，跳过")
            return img_rgba
        
        opacity = self.watermark_params.get('image_opacity', self.watermark_params.get('opacity', 0.3))
        position = self.watermark_params.get('position', 'tiled')
        
        # 读取水印图片（支持中文路径）
        try:
            # 使用numpy读取，支持中文路径
            with open(image_path, 'rb') as f:
                image_data = f.read()
            nparr = np.frombuffer(image_data, np.uint8)
            watermark = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
            if watermark is None:
                print(f"[水印] 无法解码水印图片: {image_path}")
                return img_rgba
        except Exception as e:
            print(f"[水印] 读取水印图片失败: {image_path}, 错误: {e}")
            return img_rgba
        
        # 处理去背景
        remove_bg = self.watermark_params.get('image_remove_bg', False)
        if remove_bg and watermark.shape[2] == 3:
            # 将BGR图片转为RGBA，使用简单的颜色阈值去背景
            # 检测图片四个角落的颜色，作为背景色
            h_wm, w_wm = watermark.shape[:2]
            corner_colors = [
                watermark[0, 0],           # 左上
                watermark[0, w_wm-1],      # 右上
                watermark[h_wm-1, 0],      # 左下
                watermark[h_wm-1, w_wm-1]  # 右下
            ]
            # 使用最常见的颜色作为背景色（简单处理）
            bg_color = corner_colors[0]
            
            # 创建alpha通道
            alpha = np.ones((h_wm, w_wm), dtype=np.uint8) * 255
            
            # 计算与背景色的差异
            color_diff = np.abs(watermark.astype(np.float32) - bg_color.astype(np.float32))
            color_diff = np.sum(color_diff, axis=2)
            
            # 设置阈值，与背景色相近的设为透明
            threshold = 30  # 可调节的阈值
            alpha[color_diff < threshold] = 0
            
            # 合并alpha通道
            watermark = np.dstack([watermark, alpha])
        
        h, w = img_rgba.shape[:2]
        
        if position == 'tiled':
            # 平铺模式：使用PIL实现斜向平铺
            from PIL import Image, ImageDraw, ImageFont
            import math
            
            # 转换为PIL格式
            if img_rgba.shape[2] == 4:
                img_bgr = img_rgba[:, :, :3]
                img_alpha = img_rgba[:, :, 3]
                origin_image = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
                origin_image.putalpha(Image.fromarray(img_alpha))
            else:
                origin_image = Image.fromarray(cv2.cvtColor(img_rgba, cv2.COLOR_BGR2RGB)).convert("RGBA")
            
            # 读取水印图片
            if watermark.shape[2] == 4:
                wm_bgr = watermark[:, :, :3]
                wm_alpha = watermark[:, :, 3]
                watermark_image = Image.fromarray(cv2.cvtColor(wm_bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
                watermark_image.putalpha(Image.fromarray(wm_alpha))
            else:
                watermark_image = Image.fromarray(cv2.cvtColor(watermark, cv2.COLOR_BGR2RGB)).convert("RGBA")
            
            # 设置水印透明度
            alpha_layer = watermark_image.split()[3]
            alpha_layer = alpha_layer.point(lambda p: int(p * opacity))
            watermark_image.putalpha(alpha_layer)
            
            # 获取水印大小
            scale = self.watermark_params.get('image_scale', 0.1)
            wm_w = int(w * scale)
            wm_h = int(watermark_image.size[1] * wm_w / watermark_image.size[0])
            watermark_image = watermark_image.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
            
            # 创建平铺画布（大一点以支持旋转）
            c = int(math.sqrt(origin_image.size[0] ** 2 + origin_image.size[1] ** 2))
            watermark_mask = Image.new(mode="RGBA", size=(c, c))
            
            # 获取间距参数
            space = self.watermark_params.get('space', 75)
            
            # 平铺水印
            for y in range(0, c, wm_h + space):
                for x in range(0, c, wm_w + space):
                    watermark_mask.paste(watermark_image, (x, y))
            
            # 旋转水印
            angle = self.watermark_params.get('angle', 30)
            watermark_mask = watermark_mask.rotate(angle)
            
            # 裁剪旋转后画布为中心区域（与原图同尺寸），再粘贴到 (0,0)，避免负坐标只显示一角
            ow, oh = origin_image.size[0], origin_image.size[1]
            mw, mh = watermark_mask.size[0], watermark_mask.size[1]
            left = max(0, (mw - ow) // 2)
            top = max(0, (mh - oh) // 2)
            right = min(mw, left + ow)
            bottom = min(mh, top + oh)
            crop = watermark_mask.crop((left, top, right, bottom))
            if crop.size[0] > 0 and crop.size[1] > 0:
                origin_image.paste(crop, (0, 0), crop)
            
            # 转换回数组
            result_rgb = np.array(origin_image.convert("RGB"))
            result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
            
            # 恢复alpha通道
            if img_rgba.shape[2] == 4:
                alpha_channel = np.array(origin_image.split()[3])
                result = np.dstack([result_bgr, alpha_channel])
            else:
                result = result_bgr
            
            return result
        else:
            # 单个位置模式：四个角落
            wm_h, wm_w = watermark.shape[:2]
            
            # 缩放水印
            scale = self.watermark_params.get('image_scale', 0.1)
            target_w = int(w * scale)
            target_h = int(wm_h * target_w / wm_w)
            watermark = cv2.resize(watermark, (target_w, target_h))
            
            # 处理水印alpha通道
            if watermark.shape[2] == 4:
                wm_bgr = watermark[:, :, :3]
                wm_alpha = watermark[:, :, 3:4].astype(np.float32) / 255.0 * opacity
            else:
                wm_bgr = watermark
                wm_alpha = np.ones((target_h, target_w, 1), dtype=np.float32) * opacity
            
            # 计算水印位置
            margin = 10
            if position == 'top_left':
                y1, x1 = margin, margin
            elif position == 'top_right':
                y1, x1 = margin, w - target_w - margin
            elif position == 'bottom_left':
                y1, x1 = h - target_h - margin, margin
            else:  # bottom_right
                y1, x1 = h - target_h - margin, w - target_w - margin
            
            y2 = y1 + target_h
            x2 = x1 + target_w
            
            # 检查边界
            if y1 < 0 or x1 < 0 or y2 > h or x2 > w:
                print("[水印] 图片太小，无法添加水印")
                return img_rgba
            
            # 提取原图对应区域
            if img_rgba.shape[2] == 4:
                roi = img_rgba[y1:y2, x1:x2, :3]
            else:
                roi = img_rgba[y1:y2, x1:x2]
            
            # 混合水印
            blended = (roi.astype(np.float32) * (1 - wm_alpha) + 
                       wm_bgr.astype(np.float32) * wm_alpha).astype(np.uint8)
            
            # 写回原图
            if img_rgba.shape[2] == 4:
                img_rgba[y1:y2, x1:x2, :3] = blended
            else:
                img_rgba[y1:y2, x1:x2] = blended
            
            return img_rgba