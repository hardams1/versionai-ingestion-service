from __future__ import annotations

import asyncio
import logging
import signal
from typing import TYPE_CHECKING

from app.models.enums import ProcessingStatus

if TYPE_CHECKING:
    from app.services.processor import ProcessingOrchestrator
    from app.services.queue_consumer import SQSConsumer

logger = logging.getLogger(__name__)


class Worker:
    """
    SQS polling worker with bounded concurrency and graceful shutdown.
    """

    def __init__(
        self,
        consumer: SQSConsumer,
        orchestrator: ProcessingOrchestrator,
        concurrency: int = 3,
        shutdown_timeout: int = 30,
    ) -> None:
        self._consumer = consumer
        self._orchestrator = orchestrator
        self._concurrency = concurrency
        self._shutdown_timeout = shutdown_timeout
        self._semaphore = asyncio.Semaphore(concurrency)
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._messages_processed = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def messages_processed(self) -> int:
        return self._messages_processed

    async def start(self) -> None:
        self._running = True
        self._consumer._running = True
        logger.info("Worker starting (concurrency=%d)", self._concurrency)

        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        except (NotImplementedError, RuntimeError):
            logger.debug("Signal handlers not supported in this context")

        while self._running:
            try:
                messages = await self._consumer.poll_messages()
                for msg, receipt_handle in messages:
                    await self._semaphore.acquire()
                    task = asyncio.create_task(
                        self._handle_message(msg, receipt_handle)
                    )
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Unexpected error in worker loop")
                await asyncio.sleep(2)

    async def stop(self) -> None:
        if not self._running:
            return
        logger.info("Worker stopping (waiting for %d in-flight tasks)...", len(self._tasks))
        self._running = False
        self._consumer._running = False

        if self._tasks:
            done, pending = await asyncio.wait(
                self._tasks, timeout=self._shutdown_timeout
            )
            for t in pending:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

        logger.info("Worker stopped. Total messages processed: %d", self._messages_processed)

    async def _handle_message(self, msg, receipt_handle: str) -> None:
        try:
            record = await self._orchestrator.process(msg)

            if record.status in (ProcessingStatus.COMPLETED, ProcessingStatus.SKIPPED):
                await self._consumer.delete_message(receipt_handle)
                self._messages_processed += 1
                logger.info(
                    "Message deleted (ingestion_id=%s, status=%s)",
                    msg.ingestion_id, record.status,
                )
            else:
                # Processing failed – let it return to queue after visibility timeout
                logger.warning(
                    "Processing failed for ingestion_id=%s: %s",
                    msg.ingestion_id, record.error_message,
                )
        except Exception:
            logger.exception("Unhandled error processing message ingestion_id=%s", msg.ingestion_id)
        finally:
            self._semaphore.release()
