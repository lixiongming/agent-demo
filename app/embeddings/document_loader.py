"""文档加载器

功能：
- 多格式文档解析（PDF/Word/TXT/Markdown）
- 文档分块策略
- 元数据提取
- 批量处理

功能：
- 统一文档处理接口
- 智能分块策略
- 元数据标准化
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import re
import os


@dataclass
class DocumentChunk:
    """文档分块数据结构"""
    content: str
    metadata: Dict[str, Any]
    source: str
    chunk_id: int
    doc_type: str
    page_num: Optional[int] = None
    position: Optional[int] = None


class DocumentLoader:
    """文档加载器
    
    功能：
    - 多格式支持
    - 智能分块
    - 元数据提取
    - 批量处理
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
        separators: List[str] = None
    ):
        """初始化文档加载器
        
        Args:
            chunk_size: 分块大小（字符数）
            chunk_overlap: 分块重叠
            min_chunk_size: 最小分块大小
            separators: 分隔符列表
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        
        # 默认分隔符（按优先级）
        self.separators = separators or [
            "\n\n",  # 段落
            "\n",    # 行
            "。",    # 中文句号
            ".",     # 英文句号
            "！",    # 中文感叹号
            "!",     # 英文感叹号
            "？",    # 中文问号
            "?",     # 英文问号
            "；",    # 中文分号
            ";",     # 英文分号
            "，",    # 中文逗号
            ",",     # 英文逗号
            " ",     # 空格
            ""       # 字符
        ]
    
    def load_file(
        self,
        file_path: str,
        extract_metadata: bool = True
    ) -> List[DocumentChunk]:
        """加载单个文件
        
        Args:
            file_path: 文件路径
            extract_metadata: 是否提取元数据
            
        Returns:
            文档分块列表
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 获取文件类型
        file_type = path.suffix.lower()
        
        # 根据类型选择加载方式
        if file_type == ".txt":
            return self._load_txt(file_path, extract_metadata)
        elif file_type == ".md":
            return self._load_markdown(file_path, extract_metadata)
        elif file_type == ".pdf":
            return self._load_pdf(file_path, extract_metadata)
        elif file_type in [".doc", ".docx"]:
            return self._load_word(file_path, extract_metadata)
        else:
            # 默认作为文本处理
            return self._load_txt(file_path, extract_metadata)
    
    def _load_txt(
        self,
        file_path: str,
        extract_metadata: bool
    ) -> List[DocumentChunk]:
        """加载TXT文件"""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 提取元数据
        metadata = {}
        if extract_metadata:
            path = Path(file_path)
            metadata = {
                "file_name": path.name,
                "file_path": str(path),
                "file_size": path.stat().st_size,
                "file_type": "txt",
                "created_time": path.stat().st_ctime,
                "modified_time": path.stat().st_mtime
            }
        
        # 分块
        return self._split_text(content, metadata, file_path, "txt")
    
    def _load_markdown(
        self,
        file_path: str,
        extract_metadata: bool
    ) -> List[DocumentChunk]:
        """加载Markdown文件"""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 提取元数据
        metadata = {}
        if extract_metadata:
            path = Path(file_path)
            metadata = {
                "file_name": path.name,
                "file_path": str(path),
                "file_size": path.stat().st_size,
                "file_type": "markdown",
                "created_time": path.stat().st_ctime,
                "modified_time": path.stat().st_mtime
            }
            
            # 提取标题
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if title_match:
                metadata["title"] = title_match.group(1)
        
        # 分块
        return self._split_text(content, metadata, file_path, "markdown")
    
    def _load_pdf(
        self,
        file_path: str,
        extract_metadata: bool
    ) -> List[DocumentChunk]:
        """加载PDF文件
        
        需要安装: pip install pypdf
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("请安装 pypdf: pip install pypdf")
        
        reader = PdfReader(file_path)
        
        chunks = []
        
        # 提取元数据
        metadata = {}
        if extract_metadata:
            path = Path(file_path)
            metadata = {
                "file_name": path.name,
                "file_path": str(path),
                "file_size": path.stat().st_size,
                "file_type": "pdf",
                "total_pages": len(reader.pages),
                "created_time": path.stat().st_ctime,
                "modified_time": path.stat().st_mtime
            }
            
            # 提取PDF元数据
            if reader.metadata:
                metadata["pdf_title"] = reader.metadata.get("/Title", "")
                metadata["pdf_author"] = reader.metadata.get("/Author", "")
                metadata["pdf_subject"] = reader.metadata.get("/Subject", "")
        
        # 按页提取
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            
            if page_text.strip():
                # 添加页码信息
                page_metadata = metadata.copy()
                page_metadata["page_num"] = page_num + 1
                
                # 分块
                page_chunks = self._split_text(
                    page_text,
                    page_metadata,
                    file_path,
                    "pdf"
                )
                
                # 更新分块信息
                for chunk in page_chunks:
                    chunk.page_num = page_num + 1
                
                chunks.extend(page_chunks)
        
        return chunks
    
    def _load_word(
        self,
        file_path: str,
        extract_metadata: bool
    ) -> List[DocumentChunk]:
        """加载Word文件
        
        需要安装: pip install python-docx
        """
        try:
            from docx import Document
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")
        
        doc = Document(file_path)
        
        # 提取内容
        content = "\n".join([para.text for para in doc.paragraphs])
        
        # 提取元数据
        metadata = {}
        if extract_metadata:
            path = Path(file_path)
            metadata = {
                "file_name": path.name,
                "file_path": str(path),
                "file_size": path.stat().st_size,
                "file_type": "word",
                "created_time": path.stat().st_ctime,
                "modified_time": path.stat().st_mtime
            }
            
            # 提取Word元数据
            core_props = doc.core_properties
            if core_props.title:
                metadata["word_title"] = core_props.title
            if core_props.author:
                metadata["word_author"] = core_props.author
            if core_props.subject:
                metadata["word_subject"] = core_props.subject
        
        # 分块
        return self._split_text(content, metadata, file_path, "word")
    
    def load_directory(
        self,
        directory: str,
        file_types: List[str] = None,
        recursive: bool = True
    ) -> List[DocumentChunk]:
        """加载目录下的所有文件
        
        Args:
            directory: 目录路径
            file_types: 文件类型过滤
            recursive: 是否递归
            
        Returns:
            文档分块列表
        """
        dir_path = Path(directory)
        
        if not dir_path.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")
        
        # 默认支持的文件类型
        supported_types = file_types or [".txt", ".md", ".pdf", ".doc", ".docx"]
        
        chunks = []
        
        # 遍历文件
        if recursive:
            files = dir_path.rglob("*")
        else:
            files = dir_path.glob("*")
        
        for file in files:
            if file.is_file() and file.suffix.lower() in supported_types:
                try:
                    file_chunks = self.load_file(str(file))
                    chunks.extend(file_chunks)
                except Exception as e:
                    print(f"加载文件失败: {file}, 错误: {e}")
        
        return chunks
    
    def _split_text(
        self,
        text: str,
        metadata: Dict[str, Any],
        source: str,
        doc_type: str
    ) -> List[DocumentChunk]:
        """文本分块
        
        Args:
            text: 文本内容
            metadata: 元数据
            source: 来源
            doc_type: 文档类型
            
        Returns:
            分块列表
        """
        # 按分隔符分块
        chunks = self._recursive_split(text, self.separators)
        
        # 过滤过小的分块
        chunks = [c for c in chunks if len(c) >= self.min_chunk_size]
        
        # 创建DocumentChunk对象
        result = []
        for i, chunk_content in enumerate(chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["chunk_count"] = len(chunks)
            chunk_metadata["chunk_size"] = len(chunk_content)
            
            result.append(DocumentChunk(
                content=chunk_content,
                metadata=chunk_metadata,
                source=source,
                chunk_id=i,
                doc_type=doc_type
            ))
        
        return result
    
    def _recursive_split(
        self,
        text: str,
        separators: List[str]
    ) -> List[str]:
        """递归分块
        
        Args:
            text: 文本
            separators: 分隔符列表
            
        Returns:
            分块列表
        """
        if not text:
            return []
        
        # 尝试每个分隔符
        for separator in separators:
            if separator in text:
                # 分割
                parts = text.split(separator)
                
                chunks = []
                current_chunk = ""
                
                for part in parts:
                    # 如果当前块 + 新部分不超过限制，则合并
                    if len(current_chunk) + len(part) + len(separator) <= self.chunk_size:
                        current_chunk += part + separator
                    else:
                        # 当前块达到限制，保存
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        
                        # 开始新块（考虑重叠）
                        if self.chunk_overlap > 0 and chunks:
                            # 从上一个块的末尾取重叠部分
                            overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                            overlap_text = current_chunk[overlap_start:]
                            current_chunk = overlap_text + part + separator
                        else:
                            current_chunk = part + separator
                
                # 保存最后一个块
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                return chunks
        
        # 如果没有找到分隔符，直接按大小分割
        return self._split_by_size(text)
    
    def _split_by_size(self, text: str) -> List[str]:
        """按大小分割
        
        Args:
            text: 文本
            
        Returns:
            分块列表
        """
        chunks = []
        
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i:i + self.chunk_size]
            if chunk:
                chunks.append(chunk)
        
        return chunks
    
    def get_supported_types(self) -> List[str]:
        """获取支持的文件类型"""
        return [".txt", ".md", ".pdf", ".doc", ".docx"]