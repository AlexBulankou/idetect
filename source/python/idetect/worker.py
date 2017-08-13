import logging
import os
import random
import signal
import time
from multiprocessing import Process

from idetect.model import Analysis, Session

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Worker:
    def __init__(self, status, working_status, success_status, failure_status, function, engine, max_sleep=60):
        """
        Create a Worker that looks for Analyses with a given status. When it finds one, it marks it with
        working_status and runs a function. If the function returns without an exception, it advances the Analysis to
        success_status. If the function raises an exception, it advances the Analysis to failure_status.
        """
        self.status = status
        self.working_status = working_status
        self.success_status = success_status
        self.failure_status = failure_status
        self.function = function
        self.engine = engine
        self.terminated = False
        self.max_sleep = max_sleep
        signal.signal(signal.SIGINT, self.terminate)
        signal.signal(signal.SIGTERM, self.terminate)

    def terminate(self, signum, frame):
        logger.warning("Worker {} terminated".format(os.getpid()))
        self.terminated = True

    def work(self):
        """
        Look for analyses in the given session and run function on them
        if any are found, managing status appropriately. Return True iff some Analyses were processed (successfully or not)
        """
        # start a new session for each job
        session = Session()
        try:
            # Get an analysis
            # ... and lock it for updates
            # ... that has the right status
            # ... sort by updated date
            # ... pick the first (oldest)
            analysis = session.query(Analysis) \
                .with_for_update() \
                .filter(Analysis.status == self.status) \
                .order_by(Analysis.updated) \
                .first()
            if analysis is None:
                return False  # no work to be done
            analysis.create_new_version(self.working_status)
            logger.info("Worker {} claimed Analysis {} in status {}".format(
                os.getpid(), analysis.document_id, self.status))
        finally:
            # make sure to release a FOR UPDATE lock, if we got one
            session.rollback()

        start = time.time()
        try:
            # actually run the work function on this analysis
            self.function(analysis)
            delta = time.time() - start
            logger.info("Worker {} processed Analysis {} {} -> {} {}s".format(
                os.getpid(), analysis.document_id, self.status, self.success_status, delta))
            analysis.error_msg = None
            analysis.processing_time = delta
            analysis.create_new_version(self.success_status)
        except Exception as e:
            delta = time.time() - start
            logger.warning("Worker {} failed to process Analysis {} {} -> {}".format(
                os.getpid(), analysis.document_id, self.status, self.failure_status),
                exc_info=e)
            analysis.error_msg = str(e)
            analysis.processing_time = delta
            analysis.create_new_version(self.failure_status)
            session.commit()
        finally:
            if session is not None:
                session.rollback()
                session.close()
        return True

    def work_all(self):
        """Work repeatedly until there is no work to do. Return a count of the number of units of work done"""
        count = 0
        while self.work() and not self.terminated:
            count += 1
        return count

    def work_indefinitely(self):
        """While there is work to do, do it. If there's no work to do, take increasingly long naps until there is."""
        logger.info("Worker {} working indefinitely".format(os.getpid()))
        time.sleep(random.randrange(self.max_sleep))  # stagger start times
        sleep = 1
        while not self.terminated:
            if self.work_all() > 0:
                sleep = 1
            else:
                time.sleep(sleep)
                sleep = min(self.max_sleep, sleep * 2)

    @staticmethod
    def start_processes(num, status, working_status, success_status, failure_status, function, engine, max_sleep=60):
        processes = []
        engine.dispose()  # each Worker must have its own session, made in-Process
        for i in range(num):
            worker = Worker(status, working_status, success_status, failure_status, function, engine, max_sleep)
            process = Process(target=worker.work_indefinitely, daemon=True)
            processes.append(process)
            process.start()
        return processes
