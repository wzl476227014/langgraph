"""
Parallel Slide Manager
并行幻灯片生成管理器 - 支持批量并行生成幻灯片
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional
from datetime import datetime
from .logger import get_logger
from .config import get_config

logger = get_logger(__name__)


class ParallelSlideManager:
    """并行幻灯片生成管理器"""

    def __init__(self, max_workers: int = 5):
        """
        初始化并行管理器

        Args:
            max_workers: 最大并行worker数量
        """
        self.config = get_config()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        logger.info(
            f"ParallelSlideManager initialized with {max_workers} workers",
            agent_name="ParallelSlideManager"
        )

    def generate_slides_parallel(
        self,
        slide_list: List[Dict[str, Any]],
        template_cache: Dict[str, str],
        extracted_data: Dict[str, Any],
        generator
    ) -> List[Dict[str, Any]]:
        """
        并行生成多个幻灯片(同步版本)

        Args:
            slide_list: 待生成的幻灯片信息列表
            template_cache: 模板缓存
            extracted_data: 提取的文档数据
            generator: SlideGeneratorTool实例

        Returns:
            生成结果列表
        """
        logger.info(
            f"🔄 并行生成开始: {len(slide_list)} 个页面同时处理 (max_workers={self.max_workers})",
            agent_name="ParallelSlideManager"
        )

        start_time = datetime.now()
        results = []
        failed_slides = []

        # 提交所有任务到线程池
        future_to_slide = {}
        for slide_info in slide_list:
            future = self.executor.submit(
                self._generate_single_slide_safe,
                slide_info,
                template_cache,
                extracted_data,
                generator
            )
            future_to_slide[future] = slide_info

        logger.info(
            f"✓ 已提交 {len(future_to_slide)} 个任务到线程池，等待完成...",
            agent_name="ParallelSlideManager"
        )

        # 收集结果（阻塞等待所有任务完成）
        completed_count = 0
        total_tasks = len(future_to_slide)
        for future in as_completed(future_to_slide):
            slide_info = future_to_slide[future]
            completed_count += 1
            try:
                result = future.result(timeout=9600)  # 160分钟超时
                if result["status"] == "success":
                    results.append(result)
                    logger.info(
                        f"✓ [{completed_count}/{total_tasks}] 页面 {result['page_number']} 生成成功",
                        agent_name="ParallelSlideManager"
                    )
                else:
                    failed_slides.append(slide_info["page"])
                    logger.warning(
                        f"✗ [{completed_count}/{total_tasks}] 页面 {slide_info['page']} 生成失败（状态非成功）",
                        agent_name="ParallelSlideManager"
                    )
            except Exception as e:
                failed_slides.append(slide_info["page"])
                logger.error(
                    f"✗ [{completed_count}/{total_tasks}] 页面 {slide_info['page']} 生成异常: {str(e)}",
                    agent_name="ParallelSlideManager"
                )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 按页码排序
        results.sort(key=lambda x: x["page_number"])

        logger.info(
            f"Parallel generation completed: {len(results)}/{len(slide_list)} succeeded "
            f"in {duration:.2f}s ({duration/len(slide_list):.2f}s per slide)",
            agent_name="ParallelSlideManager"
        )

        if failed_slides:
            logger.warning(
                f"Failed slides: {failed_slides}",
                agent_name="ParallelSlideManager"
            )

        return results

    async def generate_slides_parallel_async(
        self,
        slide_list: List[Dict[str, Any]],
        template_cache: Dict[str, str],
        extracted_data: Dict[str, Any],
        generator
    ) -> List[Dict[str, Any]]:
        """
        异步并行生成多个幻灯片

        Args:
            slide_list: 待生成的幻灯片信息列表
            template_cache: 模板缓存
            extracted_data: 提取的文档数据
            generator: SlideGeneratorTool实例

        Returns:
            生成结果列表
        """
        logger.info(
            f"Starting async parallel generation for {len(slide_list)} slides",
            agent_name="ParallelSlideManager"
        )

        start_time = datetime.now()

        # 创建异步任务
        tasks = []
        for slide_info in slide_list:
            task = self._generate_single_slide_async(
                slide_info,
                template_cache,
                extracted_data,
                generator
            )
            tasks.append(task)

        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        successful_results = []
        failed_slides = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_slides.append(slide_list[i]["page"])
                logger.error(
                    f"Slide {slide_list[i]['page']} async generation failed: {str(result)}",
                    agent_name="ParallelSlideManager"
                )
            elif result["status"] == "success":
                successful_results.append(result)
            else:
                failed_slides.append(slide_list[i]["page"])

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 按页码排序
        successful_results.sort(key=lambda x: x["page_number"])

        logger.info(
            f"Async parallel generation completed: {len(successful_results)}/{len(slide_list)} succeeded "
            f"in {duration:.2f}s",
            agent_name="ParallelSlideManager"
        )

        return successful_results

    def _generate_single_slide_safe(
        self,
        slide_info: Dict[str, Any],
        template_cache: Dict[str, str],
        extracted_data: Dict[str, Any],
        generator
    ) -> Dict[str, Any]:
        """
        安全地生成单个幻灯片(带异常处理)

        Args:
            slide_info: 幻灯片信息
            template_cache: 模板缓存
            extracted_data: 文档数据
            generator: 生成器实例

        Returns:
            生成结果
        """
        try:
            result = generator.generate_slide(
                slide_info,
                template_cache,
                extracted_data
            )
            return result
        except Exception as e:
            logger.error(
                f"Exception in _generate_single_slide_safe for page {slide_info['page']}: {str(e)}",
                agent_name="ParallelSlideManager"
            )
            # 返回默认幻灯片
            return generator._get_default_slide(slide_info)

    async def _generate_single_slide_async(
        self,
        slide_info: Dict[str, Any],
        template_cache: Dict[str, str],
        extracted_data: Dict[str, Any],
        generator
    ) -> Dict[str, Any]:
        """
        异步生成单个幻灯片

        Args:
            slide_info: 幻灯片信息
            template_cache: 模板缓存
            extracted_data: 文档数据
            generator: 生成器实例

        Returns:
            生成结果
        """
        # 在事件循环中运行同步函数
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._generate_single_slide_safe,
            slide_info,
            template_cache,
            extracted_data,
            generator
        )
        return result

    def generate_slides_batch(
        self,
        slide_list: List[Dict[str, Any]],
        template_cache: Dict[str, str],
        extracted_data: Dict[str, Any],
        generator,
        batch_size: int = 3
    ) -> List[Dict[str, Any]]:
        """
        分批并行生成幻灯片(避免API限流)

        Args:
            slide_list: 待生成的幻灯片列表
            template_cache: 模板缓存
            extracted_data: 文档数据
            generator: 生成器实例
            batch_size: 每批大小

        Returns:
            生成结果列表
        """
        logger.info(
            f"Starting batch generation: {len(slide_list)} slides in batches of {batch_size}",
            agent_name="ParallelSlideManager"
        )

        all_results = []

        # 分批处理
        for i in range(0, len(slide_list), batch_size):
            batch = slide_list[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(slide_list) + batch_size - 1) // batch_size

            logger.info(
                f"⏳ 开始批次 {batch_num}/{total_batches} - 处理 {len(batch)} 个页面",
                agent_name="ParallelSlideManager"
            )

            # 并行生成当前批次（会阻塞等待所有任务完成）
            batch_results = self.generate_slides_parallel(
                batch,
                template_cache,
                extracted_data,
                generator
            )

            all_results.extend(batch_results)

            logger.info(
                f"✓ 批次 {batch_num}/{total_batches} 完成 - 成功生成 {len(batch_results)}/{len(batch)} 页",
                agent_name="ParallelSlideManager"
            )

            # 批次间延迟(避免API限流)
            if i + batch_size < len(slide_list):
                import time
                delay_seconds = 2
                logger.info(
                    f"⏸ 批次间延迟 {delay_seconds} 秒后开始下一批次...",
                    agent_name="ParallelSlideManager"
                )
                time.sleep(delay_seconds)

        logger.info(
            f"Batch generation completed: {len(all_results)}/{len(slide_list)} slides generated",
            agent_name="ParallelSlideManager"
        )

        return all_results

    def shutdown(self):
        """关闭线程池"""
        self.executor.shutdown(wait=True)
        logger.info("ParallelSlideManager shutdown", agent_name="ParallelSlideManager")


class TemplateCache:
    """模板缓存管理器"""

    _cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def set_template(cls, template_key: str, template_data: Dict[str, Any]):
        """
        缓存模板

        Args:
            template_key: 模板键(如'cover', 'toc', 'content')
            template_data: 模板数据(包含html_content等)
        """
        cls._cache[template_key] = template_data
        logger.debug(f"Template '{template_key}' cached", agent_name="TemplateCache")

    @classmethod
    def get_template(cls, template_key: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存的模板

        Args:
            template_key: 模板键

        Returns:
            模板数据或None
        """
        return cls._cache.get(template_key)

    @classmethod
    def get_all_templates(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有缓存的模板"""
        return cls._cache.copy()

    @classmethod
    def clear_cache(cls):
        """清空缓存"""
        cls._cache.clear()
        logger.info("Template cache cleared", agent_name="TemplateCache")

    @classmethod
    def has_template(cls, template_key: str) -> bool:
        """检查模板是否已缓存"""
        return template_key in cls._cache
