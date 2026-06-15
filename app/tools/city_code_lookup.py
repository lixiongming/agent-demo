"""城市代码查找工具

根据城市名称查找对应的城市代码（Location_ID）
用于天气API调用
"""
import csv
import os
from typing import Dict, List, Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class CityCodeLookup:
    """城市代码查找工具
    
    从CSV文件中查找城市代码
    支持多种匹配方式：
    - 精确匹配（城市名称）
    - 模糊匹配（包含关键词）
    - 区县匹配（区县名称）
    """
    
    def __init__(self):
        self.csv_file = "data/China-City-List-latest.csv"
        self.city_data = []
        self.city_index = {}  # 城市名称索引
        self._load_city_data()
    
    def _load_city_data(self):
        """加载城市数据
        
        从CSV文件加载城市数据，并建立索引
        """
        try:
            # 获取项目根目录（app/tools 的父目录的父目录）
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            csv_path = os.path.join(project_root, "data", "China-City-List-latest.csv")
            
            logger.info(f"尝试加载城市数据文件: {csv_path}")
            
            if not os.path.exists(csv_path):
                logger.warning(f"城市数据文件不存在: {csv_path}")
                logger.warning(f"项目根目录: {project_root}")
                logger.warning(f"当前目录: {current_dir}")
                return
            
            logger.info(f"城市数据文件存在: {csv_path}")
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                # CSV第一行是列名，直接使用DictReader读取
                reader = csv.DictReader(f)
                logger.info(f"CSV列名: {reader.fieldnames}")
                
                for row in reader:
                    # 提取关键信息
                    city_info = {
                        'location_id': row.get('Location_ID', ''),
                        'name_zh': row.get('Location_Name_ZH', ''),
                        'name_en': row.get('Location_Name_EN', ''),
                        'adm1_zh': row.get('Adm1_Name_ZH', ''),  # 省市名称
                        'adm2_zh': row.get('Adm2_Name_ZH', ''),  # 区县名称
                        'latitude': row.get('Latitude', ''),
                        'longitude': row.get('Longitude', '')
                    }
                    
                    self.city_data.append(city_info)
                    
                    # 建立索引（城市名称 -> 城市代码）
                    if city_info['name_zh']:
                        self.city_index[city_info['name_zh'].lower()] = city_info['location_id']
                    
                    # 建立索引（省市名称 -> 城市代码）
                    if city_info['adm1_zh']:
                        # 只保存第一个匹配的城市代码（主要城市）
                        if city_info['adm1_zh'].lower() not in self.city_index:
                            self.city_index[city_info['adm1_zh'].lower()] = city_info['location_id']
            
            logger.info(f"已加载 {len(self.city_data)} 个城市数据")
            logger.info(f"已建立 {len(self.city_index)} 个城市索引")
        
        except Exception as e:
            logger.error(f"加载城市数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def lookup(self, city_name: str) -> Optional[str]:
        """查找城市代码
        
        Args:
            city_name: 城市名称（如：北京、上海、广州）
        
        Returns:
            城市代码（如：101010100），未找到返回None
        """
        if not city_name:
            return None
        
        # 清理城市名称
        city_name_clean = city_name.strip().lower()
        
        # 移除常见的后缀词（市、区、县等）
        suffixes = ['市', '区', '县', '镇', '乡', '街道', '新区']
        for suffix in suffixes:
            if city_name_clean.endswith(suffix):
                city_name_clean = city_name_clean[:-len(suffix)]
        
        # 1. 精确匹配（城市名称）
        if city_name_clean in self.city_index:
            city_code = self.city_index[city_name_clean]
            logger.info(f"精确匹配成功: {city_name} -> {city_code}")
            return city_code
        
        # 2. 模糊匹配（包含关键词）
        for name, code in self.city_index.items():
            if city_name_clean in name or name in city_name_clean:
                logger.info(f"模糊匹配成功: {city_name} -> {code} (匹配: {name})")
                return code
        
        # 3. 从完整数据中查找
        for city_info in self.city_data:
            # 匹配城市名称
            if city_info['name_zh'] and city_name_clean in city_info['name_zh'].lower():
                logger.info(f"数据匹配成功: {city_name} -> {city_info['location_id']} (城市: {city_info['name_zh']})")
                return city_info['location_id']
            
            # 匹配省市名称
            if city_info['adm1_zh'] and city_name_clean in city_info['adm1_zh'].lower():
                logger.info(f"省市匹配成功: {city_name} -> {city_info['location_id']} (省市: {city_info['adm1_zh']})")
                return city_info['location_id']
            
            # 匹配区县名称
            if city_info['adm2_zh'] and city_name_clean in city_info['adm2_zh'].lower():
                logger.info(f"区县匹配成功: {city_name} -> {city_info['location_id']} (区县: {city_info['adm2_zh']})")
                return city_info['location_id']
        
        logger.warning(f"未找到城市代码: {city_name}")
        return None
    
    def lookup_with_info(self, city_name: str) -> Optional[Dict]:
        """查找城市代码和详细信息
        
        Args:
            city_name: 城市名称
        
        Returns:
            城市详细信息，未找到返回None
        """
        city_code = self.lookup(city_name)
        if not city_code:
            return None
        
        # 查找详细信息
        for city_info in self.city_data:
            if city_info['location_id'] == city_code:
                return city_info
        
        return None
    
    def get_all_cities(self) -> List[Dict]:
        """获取所有城市数据
        
        Returns:
            城市列表
        """
        return self.city_data
    
    def get_major_cities(self) -> Dict[str, str]:
        """获取主要城市
        
        Returns:
            主要城市字典（城市名称 -> 城市代码）
        """
        major_cities = {
            '北京': '101010100',
            '上海': '101020100',
            '天津': '101030100',
            '重庆': '101040100',
            '广州': '101280101',
            '深圳': '101280601',
            '杭州': '101210101',
            '南京': '101190101',
            '成都': '101270101',
            '武汉': '101200101',
            '西安': '101110101',
            '苏州': '101190401',
            '郑州': '101180101',
            '长沙': '101250101',
            '青岛': '101120201',
            '大连': '101070201',
            '宁波': '101210401',
            '厦门': '101230201',
            '福州': '101230101',
            '沈阳': '101070101'
        }
        
        return major_cities


# 全局城市代码查找实例
city_code_lookup = CityCodeLookup()


def lookup_city_code(city_name: str) -> Optional[str]:
    """查找城市代码（快捷函数）
    
    Args:
        city_name: 城市名称
    
    Returns:
        城市代码
    """
    return city_code_lookup.lookup(city_name)