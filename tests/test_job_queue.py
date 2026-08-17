"""
Tests for fabric.job_queue.JobQueue.

These mostly exist to pin down how JobQueue recognises a child process. See
``fabric.tasks._multiprocessing_context`` for why parallel execution builds its
processes from an explicit context rather than ``multiprocessing.Process``.
"""

from multiprocessing.process import BaseProcess

from fabric.job_queue import JobQueue
from fabric.tasks import _multiprocessing_context

from utils import FabricTest, eq_


def _worker(queue, name):
    """
    Report a result back over the comms queue and exit cleanly.
    """
    queue.put({'name': name, 'result': 'ok'})


def _failing_worker(queue, name):
    """
    Report a result, then exit with a non-zero status.
    """
    queue.put({'name': name, 'result': 'ok'})
    raise SystemExit(3)


class TestJobQueue(FabricTest):
    def _run_job(self, name, target):
        ctx = _multiprocessing_context()
        comms = ctx.Queue()
        jobs = JobQueue(1, comms)
        process = ctx.Process(
            target=target, kwargs={'queue': comms, 'name': name}
        )
        process.name = name
        jobs.append(process)
        jobs.close()
        return jobs.run()

    def test_process_from_context_is_a_BaseProcess(self):
        """
        The type JobQueue checks against must match what tasks.py builds

        ForkProcess/SpawnProcess/... are siblings of multiprocessing.Process,
        not subclasses of it, so BaseProcess is the only ancestor they share.
        """
        ctx = _multiprocessing_context()
        process = ctx.Process(
            target=_worker, kwargs={'queue': ctx.Queue(), 'name': 'unstarted'}
        )
        assert isinstance(process, BaseProcess)

    def test_exit_code_is_attached_for_context_built_process(self):
        """
        exit_code must be filled in for processes built from a context

        If the isinstance check in JobQueue.run misses them, exit_code is left
        as None, which execute() compares against 0 and reads as a failure --
        i.e. every parallel run would be reported as having failed.
        """
        results = self._run_job('worker-ok', _worker)
        eq_(results['worker-ok']['exit_code'], 0)
        eq_(results['worker-ok']['results'], 'ok')

    def test_nonzero_exit_code_is_reported(self):
        """
        A child that dies with a non-zero status keeps that status
        """
        results = self._run_job('worker-fail', _failing_worker)
        eq_(results['worker-fail']['exit_code'], 3)
