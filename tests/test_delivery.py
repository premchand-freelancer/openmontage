import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('workflow', Path(__file__).resolve().parents[1] / 'scripts/openmontage.py')
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory(prefix='openmontage-tests-')
        cls.root = Path(cls.storage.name)
        cls.video = cls.root / 'silent.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                        'testsrc2=size=640x360:rate=30', '-t', '2', '-c:v', 'libx264',
                        '-threads', '2', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', str(cls.video)], check=True)
        cls.audio_video = cls.root / 'with-audio.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(cls.video),
                        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '2',
                        '-c:v', 'copy', '-c:a', 'aac', str(cls.audio_video)], check=True)
        cls.expected = dict(duration=2, width=640, height=360, fps=30, audio='none')
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(cls.video),
                        '-vf', "select='eq(n,0)+eq(n,15)+eq(n,30)+eq(n,59)',scale=160:90",
                        '-fps_mode', 'vfr', '-threads', '1', str(cls.root / 'frame-%02d.png')], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.storage.cleanup()

    def review(self, directory, **changes):
        result = {'status': 'pass', 'output_path': str(self.video), 'metadata': {'export_sha256': workflow.sha256(self.video)}, 'checks': {'visual_spotcheck': {
            'frames_sampled': 4, 'frame_paths': [str(self.root / f'frame-{i:02d}.png') for i in range(1, 5)],
            'black_frames_detected': False, 'broken_overlays': False,
            'missing_assets': False, 'unreadable_text': False}}}
        result.update(changes)
        file = Path(directory) / 'review.json'
        file.write_text(json.dumps(result))
        return file

    def test_full_decode_and_video_contract(self):
        actual = workflow.verify_video(self.video, **self.expected)
        self.assertEqual(actual['frames'], 60)
        self.assertEqual(actual['audio_streams'], 0)
        self.assertTrue(actual['full_decode_passed'])
        self.assertEqual(actual['sha256'], hashlib.sha256(self.video.read_bytes()).hexdigest())

    def test_wrong_duration_dimensions_and_fps_are_rejected(self):
        for replacement in ({'duration': 3}, {'width': 1080}, {'fps': 24}):
            with self.subTest(replacement=replacement), self.assertRaises(workflow.WorkflowError):
                workflow.verify_video(self.video, **(self.expected | replacement))

    def test_silent_and_required_audio_contracts(self):
        with self.assertRaises(workflow.WorkflowError):
            workflow.verify_video(self.video, **(self.expected | {'audio': 'required'}))
        with self.assertRaises(workflow.WorkflowError):
            workflow.verify_video(self.audio_video, **self.expected)
        result = workflow.verify_video(self.audio_video, **(self.expected | {'audio': 'required'}))
        self.assertEqual(result['audio_streams'], 1)

    def test_corrupt_video_is_rejected(self):
        corrupt = self.root / 'corrupt.mp4'
        corrupt.write_bytes(self.video.read_bytes()[:100])
        with self.assertRaises(workflow.WorkflowError):
            workflow.verify_video(corrupt, **self.expected)

    def test_review_must_pass_and_match_the_video(self):
        with tempfile.TemporaryDirectory() as directory:
            for replacement in ({'status': 'revise'}, {'output_path': str(self.audio_video)}):
                with self.subTest(replacement=replacement), self.assertRaises(workflow.WorkflowError):
                    workflow.require_review(self.review(directory, **replacement), self.video)

    def test_review_frames_must_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            file = self.review(directory)
            review = json.loads(file.read_text())
            review['checks']['visual_spotcheck']['frame_paths'][0] = str(self.root / 'missing.png')
            file.write_text(json.dumps(review))
            with self.assertRaises(workflow.WorkflowError):
                workflow.require_review(file, self.video)

    def test_stale_review_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            file = self.review(directory, metadata={'export_sha256': '0' * 64})
            with self.assertRaises(workflow.WorkflowError):
                workflow.require_review(file, self.video)

    def test_download_mismatch_is_not_a_verified_link(self):
        response = io.BytesIO(b'wrong download')
        response.status = 200
        with patch.object(workflow.urllib.request, 'urlopen', return_value=response), self.assertRaises(workflow.WorkflowError):
            workflow.download_matches('https://github.com/test/test/raw/commit/video.mp4', workflow.sha256(self.video), self.video.stat().st_size)

    def test_transient_download_error_is_retried_and_verified(self):
        response = io.BytesIO(self.video.read_bytes())
        response.status = 200
        with patch.object(workflow.urllib.request, 'urlopen', side_effect=[urllib.error.URLError('transient'), response]) as request, patch.object(workflow.time, 'sleep'):
            workflow.download_matches('https://github.com/test/test/raw/commit/video.mp4', workflow.sha256(self.video), self.video.stat().st_size)
        self.assertEqual(request.call_count, 2)

    def test_project_path_traversal_is_rejected(self):
        for project in ('../outside', '/tmp/outside', 'two words', 'Name', '-bad'):
            with self.subTest(project=project), self.assertRaises(workflow.WorkflowError):
                workflow.slug(project)

    def git_fixture(self, directory):
        directory = Path(directory)
        remote = directory / 'remote.git'
        repo = directory / 'checkout'
        workflow.run(['git', 'init', '--bare', str(remote)])
        workflow.run(['git', 'init', '-b', 'main', str(repo)])
        for key, value in (('user.name', 'Test'), ('user.email', 'test@example.invalid')):
            workflow.run(['git', '-C', str(repo), 'config', key, value])
        (repo / 'user.txt').write_text('original\n')
        workflow.run(['git', '-C', str(repo), 'add', 'user.txt'])
        workflow.run(['git', '-C', str(repo), 'commit', '-m', 'Initial'])
        workflow.run(['git', '-C', str(repo), 'remote', 'add', 'origin', str(remote)])
        workflow.run(['git', '-C', str(repo), 'push', 'origin', 'main'])
        (repo / 'user.txt').write_text('user staged content\n')
        workflow.run(['git', '-C', str(repo), 'add', 'user.txt'])
        (repo / 'untracked.txt').write_text('preserve this\n')
        return repo, remote

    def test_publisher_preserves_user_index_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, remote = self.git_fixture(directory)
            staged_before = workflow.run(['git', '-C', str(repo), 'diff', '--cached'])
            file = self.review(directory)
            target = ('premchand-freelancer/openmontage', 'main', Path('videos'))
            with patch.object(workflow, 'check_target', return_value=target), patch.object(workflow, 'download_matches') as download:
                receipt = workflow.publish(self.video, file, 'test-project', self.expected, repo=repo)
                second = workflow.publish(self.video, file, 'test-project', self.expected, repo=repo)
            self.assertEqual(receipt['commit'], second['commit'])
            self.assertEqual(staged_before, workflow.run(['git', '-C', str(repo), 'diff', '--cached']))
            self.assertEqual((repo / 'untracked.txt').read_text(), 'preserve this\n')
            self.assertIn(f"/raw/{receipt['commit']}/videos/", receipt['download_url'])
            content = subprocess.check_output(['git', '-C', str(remote), 'show', f"main:{receipt['repository_path']}"])
            self.assertEqual(content, self.video.read_bytes())
            download.assert_called_with(second['download_url'], workflow.sha256(self.video), self.video.stat().st_size)

    def test_concurrent_update_is_retried_without_losing_remote_files(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, remote = self.git_fixture(directory)
            file = self.review(directory)
            original_run = subprocess.run
            raced = False

            def run_with_race(args, *positional, **kwargs):
                nonlocal raced
                if 'push' in args and str(repo) in args and not raced:
                    raced = True
                    other = Path(directory) / 'other'
                    original_run(['git', 'clone', '-b', 'main', str(remote), str(other)], capture_output=True, check=True)
                    original_run(['git', '-C', str(other), 'config', 'user.name', 'Other'], check=True)
                    original_run(['git', '-C', str(other), 'config', 'user.email', 'other@example.invalid'], check=True)
                    (other / 'concurrent.txt').write_text('keep concurrent update\n')
                    for command in (['add', 'concurrent.txt'], ['commit', '-m', 'Concurrent'], ['push', 'origin', 'main']):
                        original_run(['git', '-C', str(other)] + command, capture_output=True, check=True)
                return original_run(args, *positional, **kwargs)

            with patch.object(workflow, 'check_target', return_value=('premchand-freelancer/openmontage', 'main', Path('videos'))), patch.object(workflow, 'download_matches'), patch.object(workflow.subprocess, 'run', side_effect=run_with_race):
                receipt = workflow.publish(self.video, file, 'race-project', self.expected, repo=repo)
            self.assertTrue(raced)
            self.assertEqual(workflow.run(['git', '-C', str(remote), 'show', 'main:concurrent.txt']), 'keep concurrent update')
            content = subprocess.check_output(['git', '-C', str(remote), 'show', f"main:{receipt['repository_path']}"])
            self.assertEqual(content, self.video.read_bytes())

    def test_destination_and_size_restrictions(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, _ = self.git_fixture(directory)
            with self.assertRaises(workflow.WorkflowError):
                workflow.check_target(repo, workflow.config()['delivery'])
            settings = workflow.config()
            settings['delivery']['maximum_file_bytes'] = 10
            with patch.object(workflow, 'check_target', return_value=('premchand-freelancer/openmontage', 'main', Path('videos'))), self.assertRaises(workflow.WorkflowError):
                workflow.publish(self.video, self.review(directory), 'too-large', self.expected, repo=repo, settings=settings)


if __name__ == '__main__':
    unittest.main()
