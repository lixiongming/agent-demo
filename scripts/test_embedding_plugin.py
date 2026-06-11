"""测试 Embedding 插件化架构

功能：
- 测试插件注册表
- 测试配置驱动的 Provider 切换
- 测试智谱 AI embedding-3
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接导入 providers.py，避免导入 __init__.py 中的 qdrant_store
import importlib.util
spec = importlib.util.spec_from_file_location(
    "providers",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "app", "embeddings", "providers.py")
)
providers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(providers)

EmbeddingProviderRegistry = providers.EmbeddingProviderRegistry

from app.config import get_settings


def get_embedding_service(provider: str = None, **kwargs):
    """获取 Embedding 服务实例（简化版）"""
    settings = get_settings()
    provider_name = provider or settings.EMBEDDING_PROVIDER
    
    if not provider_name:
        raise ValueError(
            "EMBEDDING_PROVIDER not configured. "
            "Please set EMBEDDING_PROVIDER in .env file."
        )
    
    return EmbeddingProviderRegistry.create_service(provider_name, **kwargs)


def list_embedding_providers():
    """列出所有可用的 Embedding 提供商"""
    return EmbeddingProviderRegistry.list_providers()


async def test_provider_registry():
    """测试插件注册表"""
    print("\n" + "="*60)
    print("测试 1: 插件注册表")
    print("="*60)
    
    # 列出所有已注册的 Provider
    providers = list_embedding_providers()
    print(f"\n已注册的 Provider 数量: {len(providers)}")
    
    for name, info in providers.items():
        print(f"\nProvider: {name}")
        print(f"  - 描述: {info.get('description', 'N/A')}")
        print(f"  - 默认模型: {info.get('default_model', 'N/A')}")
        print(f"  - 向量维度: {info.get('embedding_dim', 'N/A')}")
        print(f"  - 支持批量: {info.get('supports_batch', False)}")
        print(f"  - 支持缓存: {info.get('supports_cache', False)}")
        print(f"  - 需要配置: {info.get('requires', [])}")
    
    return True


async def test_config_driven_provider():
    """测试配置驱动的 Provider"""
    print("\n" + "="*60)
    print("测试 2: 配置驱动的 Provider")
    print("="*60)
    
    settings = get_settings()
    print(f"\n当前配置:")
    print(f"  - EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}")
    print(f"  - EMBEDDING_MODEL_NAME: {settings.EMBEDDING_MODEL_NAME}")
    print(f"  - ZHIPU_API_KEY: {'已配置' if settings.ZHIPU_API_KEY else '未配置'}")
    
    # 使用默认配置创建服务
    try:
        service = get_embedding_service()
        print(f"\n成功创建服务: {type(service).__name__}")
        print(f"  - 模型信息: {service.get_model_info()}")
        return True
    except Exception as e:
        print(f"\n创建服务失败: {e}")
        return False


async def test_zhipu_embedding():
    """测试智谱 AI Embedding"""
    print("\n" + "="*60)
    print("测试 3: 智谱 AI Embedding-3")
    print("="*60)
    
    settings = get_settings()
    
    if not settings.ZHIPU_API_KEY:
        print("\n警告: ZHIPU_API_KEY 未配置，跳过测试")
        return True
    
    try:
        # 创建服务
        service = get_embedding_service(provider='zhipu')
        print(f"\n服务类型: {type(service).__name__}")
        print(f"模型信息: {service.get_model_info()}")
        
        # 测试单文本向量化
        print("\n测试单文本向量化...")
        text = "这是一个测试文本，用于验证智谱 AI embedding-3 模型"
        embedding = await service.embed_text(text)
        print(f"  - 输入文本: {text}")
        print(f"  - 向量维度: {len(embedding)}")
        print(f"  - 向量类型: {type(embedding)}")
        
        # 测试批量向量化
        print("\n测试批量向量化...")
        texts = [
            "第一段文本",
            "第二段文本",
            "第三段文本"
        ]
        embeddings = await service.embed_texts(texts)
        print(f"  - 输入文本数量: {len(texts)}")
        print(f"  - 输出向量数量: {len(embeddings)}")
        print(f"  - 向量维度: {embeddings.shape}")
        
        # 测试相似度计算
        print("\n测试相似度计算...")
        vec1 = embeddings[0]
        vec2 = embeddings[1]
        similarity = service.similarity(vec1, vec2, metric='cosine')
        print(f"  - 文本1: {texts[0]}")
        print(f"  - 文本2: {texts[1]}")
        print(f"  - 相似度: {similarity:.4f}")
        
        # 关闭服务
        await service.close()
        print("\n服务已关闭")
        
        return True
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_provider_switching():
    """测试 Provider 切换"""
    print("\n" + "="*60)
    print("测试 4: Provider 切换")
    print("="*60)
    
    # 测试指定 Provider
    print("\n尝试创建不同 Provider 的服务:")
    
    # 智谱 AI
    print("\n1. zhipu Provider:")
    try:
        service = get_embedding_service(provider='zhipu')
        print(f"   成功: {type(service).__name__}")
    except Exception as e:
        print(f"   失败: {e}")
    
    # OpenAI（需要 API Key）
    print("\n2. openai Provider:")
    try:
        service = get_embedding_service(provider='openai')
        print(f"   成功: {type(service).__name__}")
    except ImportError as e:
        print(f"   跳过: 缺少依赖 - {e}")
    except Exception as e:
        print(f"   失败: {e}")
    
    # 本地模型（需要下载）
    print("\n3. local Provider:")
    try:
        service = get_embedding_service(provider='local')
        print(f"   成功: {type(service).__name__}")
    except ImportError as e:
        print(f"   跳过: 缺少依赖 - {e}")
    except Exception as e:
        print(f"   失败: {e}")
    
    # 不存在的 Provider
    print("\n4. unknown Provider:")
    try:
        service = get_embedding_service(provider='unknown')
        print(f"   成功: {type(service).__name__}")
    except ValueError as e:
        print(f"   预期错误: {e}")
    
    return True


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Embedding 插件化架构测试")
    print("="*60)
    
    results = []
    
    # 测试 1: 插件注册表
    result1 = await test_provider_registry()
    results.append(("插件注册表", result1))
    
    # 测试 2: 配置驱动的 Provider
    result2 = await test_config_driven_provider()
    results.append(("配置驱动", result2))
    
    # 测试 3: 智谱 AI Embedding
    result3 = await test_zhipu_embedding()
    results.append(("智谱 AI Embedding", result3))
    
    # 测试 4: Provider 切换
    result4 = await test_provider_switching()
    results.append(("Provider 切换", result4))
    
    # 输出测试结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")
    
    # 输出配置说明
    print("\n" + "="*60)
    print("配置说明")
    print("="*60)
    print("""
切换 Embedding Provider 只需修改 .env 文件：

# 使用智谱 AI（推荐中文场景）
EMBEDDING_PROVIDER=zhipu
EMBEDDING_MODEL_NAME=embedding-3
ZHIPU_API_KEY=your_zhipu_api_key

# 使用 OpenAI
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL_NAME=text-embedding-3-small
OPENAI_API_KEY=your_openai_api_key

# 使用本地模型
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL_NAME=BAAI/bge-large-zh-v1.5

无需修改代码，无需重建容器！
""")


if __name__ == "__main__":
    asyncio.run(main())