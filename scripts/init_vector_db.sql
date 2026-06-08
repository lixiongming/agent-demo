-- =============================================
-- 向量数据库表结构
-- 数据库: agent_db (与聊天Agent共用)
-- =============================================

-- 使用agent_db数据库
USE agent_db;

-- =============================================
-- 1. 向量文档表 (核心表)
-- =============================================
CREATE TABLE IF NOT EXISTS vector_documents (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '文档ID',
    content TEXT NOT NULL COMMENT '文档内容',
    embedding LONGBLOB NULL COMMENT '向量嵌入（二进制存储）',
    metadata JSON NULL COMMENT '元数据（JSON格式）',
    source VARCHAR(255) NULL COMMENT '文档来源',
    doc_type VARCHAR(50) DEFAULT 'text' COMMENT '文档类型: text/pdf/word/markdown',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX idx_doc_type (doc_type),
    INDEX idx_source (source),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='向量文档表';

-- =============================================
-- 2. 文档分块表 (可选 - 用于大文档分块管理)
-- =============================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '分块ID',
    doc_id INT NOT NULL COMMENT '文档ID',
    chunk_index INT NOT NULL COMMENT '分块索引',
    chunk_content TEXT NOT NULL COMMENT '分块内容',
    chunk_embedding LONGBLOB NULL COMMENT '分块向量',
    page_num INT NULL COMMENT '页码（PDF）',
    position INT NULL COMMENT '位置',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    INDEX idx_doc_id (doc_id),
    INDEX idx_chunk_index (chunk_index),
    
    FOREIGN KEY (doc_id) REFERENCES vector_documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档分块表';

-- =============================================
-- 3. 检索日志表 (可选 - 用于检索分析)
-- =============================================
CREATE TABLE IF NOT EXISTS retrieval_logs (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '日志ID',
    query_text TEXT NOT NULL COMMENT '查询文本',
    query_embedding LONGBLOB NULL COMMENT '查询向量',
    top_k INT DEFAULT 5 COMMENT '返回数量',
    threshold FLOAT DEFAULT 0.5 COMMENT '相似度阈值',
    result_count INT DEFAULT 0 COMMENT '结果数量',
    search_type VARCHAR(20) DEFAULT 'vector' COMMENT '检索类型: vector/hybrid/keyword',
    session_id VARCHAR(64) NULL COMMENT '会话ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    INDEX idx_session_id (session_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='检索日志表';

-- =============================================
-- 4. 向量索引表 (可选 - 用于向量索引管理)
-- =============================================
CREATE TABLE IF NOT EXISTS vector_indexes (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '索引ID',
    index_name VARCHAR(100) NOT NULL COMMENT '索引名称',
    index_type VARCHAR(50) DEFAULT 'faiss' COMMENT '索引类型: faiss/hnsw/ivf',
    doc_count INT DEFAULT 0 COMMENT '文档数量',
    dimension INT DEFAULT 1024 COMMENT '向量维度',
    index_path VARCHAR(255) NULL COMMENT '索引文件路径',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    UNIQUE KEY uk_index_name (index_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='向量索引表';

-- =============================================
-- 查看表结构
-- =============================================
SHOW TABLES;

-- 查看vector_documents表结构
DESCRIBE vector_documents;

-- =============================================
-- 示例数据插入
-- =============================================
-- 插入测试文档（注意：实际向量需要通过程序生成）
INSERT INTO vector_documents (content, source, doc_type, metadata) VALUES
('Python是一种流行的编程语言，广泛用于Web开发、数据分析和人工智能。', 'test_doc', 'text', '{"topic": "python", "author": "test"}'),
('机器学习是人工智能的一个分支，通过算法让计算机从数据中学习。', 'test_doc', 'text', '{"topic": "ml", "author": "test"}'),
('向量数据库用于存储和检索高维向量，支持相似度搜索。', 'test_doc', 'text', '{"topic": "vector_db", "author": "test"}');

-- 查询数据
SELECT id, content, source, doc_type, created_at FROM vector_documents;

-- =============================================
-- 统计查询
-- =============================================
SELECT 
    doc_type,
    COUNT(*) as count
FROM vector_documents
GROUP BY doc_type;

-- =============================================
-- 清理测试数据
-- =============================================
-- DELETE FROM vector_documents WHERE source = 'test_doc';