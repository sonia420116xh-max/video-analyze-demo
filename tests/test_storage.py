import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import backend.main as main


class AnalysisStorageTest(unittest.TestCase):
    def test_gpt4o_uses_gptproto_responses_api_with_input_images(self):
        visual_frames = [
            {
                "id": "F01",
                "timestamp": 1.2,
                "data_url": "data:image/jpeg;base64,abc",
            }
        ]
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"output_text": '[{"title":"故事开场"}]'}

        with patch.object(main, "GPTPROTO_API_KEY", "gptproto-key"), \
             patch.object(main, "GPTPROTO_VISION_MODEL", "gpt-4o"), \
             patch.object(main, "sample_visual_frames", return_value=visual_frames), \
             patch.object(main, "build_analysis_prompt", return_value="PROMPT"), \
             patch("backend.main.requests.post", return_value=response) as post:
            result = main.analyze_video("TRANSCRIPT", "gpt-4o", "/tmp/demo.mp4")

        self.assertEqual(result, '[{"title":"故事开场"}]')
        url = post.call_args.args[0]
        payload = post.call_args.kwargs["json"]
        self.assertEqual(url, "https://gptproto.com/v1/responses")
        self.assertEqual(payload["model"], "gpt-4o")
        self.assertEqual(payload["input"][0]["role"], "user")
        content = payload["input"][0]["content"]
        self.assertEqual(content[0], {"type": "input_text", "text": "PROMPT"})
        self.assertIn({"type": "input_image", "image_url": "data:image/jpeg;base64,abc"}, content)

    def test_gemini_keeps_gemini_model_when_visual_frames_exist(self):
        visual_frames = [
            {
                "id": "F01",
                "timestamp": 1.2,
                "data_url": "data:image/jpeg;base64,abc",
            }
        ]
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": '[{"title":"故事开场"}]'}}]
        }

        with patch.object(main, "GPTPROTO_API_KEY", "gptproto-key"), \
             patch.object(main, "BRAIN_MODEL", "gemini-2.5-pro"), \
             patch.object(main, "GPTPROTO_VISION_MODEL", "gpt-4o"), \
             patch.object(main, "sample_visual_frames", return_value=visual_frames), \
             patch.object(main, "build_analysis_prompt", return_value="PROMPT"), \
             patch("backend.main.requests.post", return_value=response) as post:
            result = main.analyze_video("TRANSCRIPT", "gemini-2.5-pro", "/tmp/demo.mp4")

        self.assertEqual(result, '[{"title":"故事开场"}]')
        payload = post.call_args.kwargs["json"]
        self.assertEqual(post.call_args.args[0], "https://gptproto.com/v1/chat/completions")
        self.assertEqual(payload["model"], "gemini-2.5-pro")

    def test_claude_uses_gptproto_chat_completions_with_file_images(self):
        visual_frames = [
            {
                "id": "F01",
                "timestamp": 1.2,
                "data_url": "data:image/jpeg;base64,abc",
            }
        ]
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": '[{"title":"故事开场"}]'}}]
        }

        with patch.object(main, "GPTPROTO_API_KEY", "gptproto-key"), \
             patch.object(main, "sample_visual_frames", return_value=visual_frames), \
             patch.object(main, "build_analysis_prompt", return_value="PROMPT"), \
             patch("backend.main.requests.post", return_value=response) as post:
            result = main.analyze_video("TRANSCRIPT", "claude-sonnet-4-5-20250929", "/tmp/demo.mp4")

        self.assertEqual(result, '[{"title":"故事开场"}]')
        payload = post.call_args.kwargs["json"]
        self.assertEqual(post.call_args.args[0], "https://gptproto.com/v1/chat/completions")
        self.assertEqual(payload["model"], "claude-sonnet-4-5-20250929")
        content = payload["messages"][0]["content"]
        self.assertEqual(content[0], {"type": "text", "text": "PROMPT"})
        self.assertIn({
            "type": "file",
            "file": {
                "filename": "F01.jpg",
                "file_data": "data:image/jpeg;base64,abc",
            },
        }, content)

    def test_available_model_options_empty_when_no_keys_are_configured(self):
        with patch.object(main, "GPTPROTO_API_KEY", ""), \
             patch.object(main, "OPENAI_API_KEY", ""), \
             patch.object(main, "DASHSCOPE_KEY", ""), \
             patch.object(main, "BAIDU_KEY", ""):
            options = main.get_available_model_options()

        self.assertEqual(options, [])

    def test_available_model_options_hide_unconfigured_or_unimplemented_models(self):
        with patch.object(main, "GPTPROTO_API_KEY", "gptproto-key"), \
             patch.object(main, "OPENAI_API_KEY", ""), \
             patch.object(main, "DASHSCOPE_KEY", ""), \
             patch.object(main, "BAIDU_KEY", ""):
            options = main.get_available_model_options()

        values = [option["value"] for option in options]
        labels = [option["label"] for option in options]
        self.assertEqual(values, ["gemini-2.5-pro", "gpt-4o", "claude-sonnet-4-5-20250929"])
        self.assertEqual(labels, values)
        self.assertNotIn("gptproto", values)
        self.assertNotIn("gptproto-gpt4o", values)
        self.assertNotIn("gpt4o", values)
        self.assertNotIn("tongyi", values)
        self.assertNotIn("baidu", values)

    def test_available_model_options_include_openai_and_tongyi_when_keys_exist(self):
        with patch.object(main, "GPTPROTO_API_KEY", ""), \
             patch.object(main, "OPENAI_API_KEY", "openai-key"), \
             patch.object(main, "DASHSCOPE_KEY", "dashscope-key"), \
             patch.object(main, "BAIDU_KEY", "baidu-key"):
            options = main.get_available_model_options()

        values = [option["value"] for option in options]
        labels = [option["label"] for option in options]
        self.assertEqual(values, ["qwen-turbo"])
        self.assertEqual(labels, values)
        self.assertNotIn("baidu", values)

    def test_save_list_and_detail_analysis_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analysis.db"
            main.init_db(db_path)

            record = {
                "id": "analysis-1",
                "filename": "demo.mp4",
                "model": "gemini-2.5-pro",
                "video_path": "/tmp/demo.mp4",
                "video_url": "/storage/videos/demo.mp4",
                "result_json": json.dumps([
                    {
                        "viral_formula": "分屏对比",
                        "formula_subtype": "前后分屏型",
                        "category_reason": "两个产品并列比较。",
                    }
                ], ensure_ascii=False),
                "formula": "分屏对比",
                "subtype": "前后分屏型",
                "category_reason": "两个产品并列比较。",
                "created_at": "2026-05-11T10:00:00+08:00",
            }

            main.save_analysis_record(record, db_path)

            records = main.fetch_analysis_list(db_path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["id"], "analysis-1")
            self.assertEqual(records[0]["shot_count"], 1)
            self.assertEqual(records[0]["cover_url"], "")

            detail = main.fetch_analysis_detail("analysis-1", db_path)
            self.assertEqual(detail["filename"], "demo.mp4")
            self.assertEqual(detail["data"][0]["formula_subtype"], "前后分屏型")

    def test_fetch_analysis_list_includes_pending_initial_upload_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analysis.db"
            main.init_db(db_path)
            created_at = "2026-05-11T10:00:00+08:00"
            with main._connect_db(db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO analysis_jobs (
                        job_id, status, filename, model, message,
                        cancel_requested, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        "job-1",
                        "queued",
                        "uploading-demo.mp4",
                        "gemini-2.5-pro",
                        "任务已提交，等待后台分析",
                        created_at,
                        created_at,
                    ),
                )
                conn.commit()

            records = main.fetch_analysis_list(db_path)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["id"], "job-1")
            self.assertTrue(records[0]["is_pending_job"])
            self.assertEqual(records[0]["job_id"], "job-1")
            self.assertEqual(records[0]["status"], "queued")
            self.assertEqual(records[0]["filename"], "uploading-demo.mp4")
            self.assertEqual(records[0]["shot_count"], 0)

    def test_fetch_analysis_list_excludes_terminal_jobs_without_analysis_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analysis.db"
            main.init_db(db_path)
            created_at = "2026-05-11T10:00:00+08:00"
            with main._connect_db(db_path) as conn:
                for job_id, status in [("job-failed", "failed"), ("job-canceled", "canceled")]:
                    conn.execute(
                        """
                        INSERT INTO analysis_jobs (
                            job_id, status, filename, model, message,
                            cancel_requested, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (
                            job_id,
                            status,
                            f"{status}.mp4",
                            "gemini-2.5-pro",
                            "terminal job",
                            created_at,
                            created_at,
                        ),
                    )
                conn.commit()

            self.assertEqual(main.fetch_analysis_list(db_path), [])

    def test_update_analysis_record_replaces_existing_result_without_new_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "analysis.db"
            stored_frames = root / "stored-frames"
            temp_frames = root / "temp-frames"
            stored_frames.mkdir()
            temp_frames.mkdir()
            (temp_frames / "shot_01.jpg").write_bytes(b"new frame")
            main.init_db(db_path)
            main.save_analysis_record(
                {
                    "id": "analysis-1",
                    "filename": "demo.mp4",
                    "model": "gemini-2.5-pro",
                    "video_path": str(root / "demo.mp4"),
                    "video_url": "/storage/videos/demo.mp4",
                    "result_json": "[]",
                    "formula": "",
                    "subtype": "",
                    "category_reason": "",
                    "created_at": "2026-05-11T10:00:00+08:00",
                },
                db_path,
            )
            result_json = json.dumps([
                {
                    "viral_formula": "开箱 / ASMR",
                    "formula_subtype": "开箱评测型",
                    "category_reason": "重新生成后的结果。",
                    "image_url": "/frames/shot_01.jpg",
                }
            ], ensure_ascii=False)

            updated = main.update_analysis_record_result(
                "analysis-1",
                "gpt4o",
                result_json,
                db_path=db_path,
                stored_frame_dir=stored_frames,
                temp_frame_dir=temp_frames,
            )

            self.assertEqual(updated["analysis_id"], "analysis-1")
            detail = main.fetch_analysis_detail("analysis-1", db_path)
            self.assertEqual(detail["model"], "gpt4o")
            self.assertEqual(detail["shot_count"], 1)
            self.assertEqual(detail["data"][0]["formula_subtype"], "开箱评测型")
            self.assertEqual(detail["data"][0]["image_url"], "/storage/frames/analysis-1/gpt4o/shot_01.jpg")
            self.assertEqual((stored_frames / "analysis-1" / "gpt4o" / "shot_01.jpg").read_bytes(), b"new frame")

    def test_update_analysis_record_preserves_latest_result_per_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "analysis.db"
            stored_frames = root / "stored-frames"
            temp_frames = root / "temp-frames"
            stored_frames.mkdir()
            temp_frames.mkdir()
            (temp_frames / "shot_01.jpg").write_bytes(b"gpt frame")
            main.init_db(db_path)
            main.save_analysis_record(
                {
                    "id": "analysis-1",
                    "filename": "demo.mp4",
                    "model": "gemini-2.5-pro",
                    "video_path": str(root / "demo.mp4"),
                    "video_url": "/storage/videos/demo.mp4",
                    "result_json": json.dumps([
                        {
                            "viral_formula": "日常 Vlog",
                            "formula_subtype": "日常碎片型",
                            "category_reason": "gemini 版本",
                        }
                    ], ensure_ascii=False),
                    "formula": "日常 Vlog",
                    "subtype": "日常碎片型",
                    "category_reason": "gemini 版本",
                    "created_at": "2026-05-11T10:00:00+08:00",
                },
                db_path,
            )

            updated = main.update_analysis_record_result(
                "analysis-1",
                "gpt-4o",
                json.dumps([
                    {
                        "viral_formula": "分屏对比",
                        "formula_subtype": "平替对决型",
                        "category_reason": "gpt 版本",
                        "image_url": "/frames/shot_01.jpg",
                    }
                ], ensure_ascii=False),
                db_path=db_path,
                stored_frame_dir=stored_frames,
                temp_frame_dir=temp_frames,
            )

            self.assertEqual(updated["analysis_id"], "analysis-1")
            detail = main.fetch_analysis_detail("analysis-1", db_path)
            self.assertEqual(detail["model"], "gpt-4o")
            self.assertEqual(detail["data"][0]["formula_subtype"], "平替对决型")
            self.assertEqual([version["model"] for version in detail["versions"]], ["gpt-4o", "gemini-2.5-pro"])
            version_by_model = {version["model"]: version for version in detail["versions"]}
            self.assertEqual(version_by_model["gemini-2.5-pro"]["data"][0]["formula_subtype"], "日常碎片型")
            self.assertEqual(version_by_model["gpt-4o"]["data"][0]["image_url"], "/storage/frames/analysis-1/gpt-4o/shot_01.jpg")
            self.assertEqual((stored_frames / "analysis-1" / "gpt-4o" / "shot_01.jpg").read_bytes(), b"gpt frame")

            records = main.fetch_analysis_list(db_path)
            self.assertEqual(records[0]["cover_url"], "/storage/frames/analysis-1/gpt-4o/shot_01.jpg")

    def test_delete_analysis_record_removes_db_row_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "analysis.db"
            video_path = root / "videos" / "demo.mp4"
            frame_dir = root / "frames" / "analysis-1"
            video_path.parent.mkdir()
            frame_dir.mkdir(parents=True)
            video_path.write_bytes(b"video")
            (frame_dir / "shot_01.jpg").write_bytes(b"frame")
            main.init_db(db_path)
            main.save_analysis_record(
                {
                    "id": "analysis-1",
                    "filename": "demo.mp4",
                    "model": "gemini-2.5-pro",
                    "video_path": str(video_path),
                    "video_url": "/storage/videos/demo.mp4",
                    "result_json": "[]",
                    "formula": "",
                    "subtype": "",
                    "category_reason": "",
                    "created_at": "2026-05-11T10:00:00+08:00",
                },
                db_path,
            )

            deleted = main.delete_analysis_record(
                "analysis-1",
                db_path=db_path,
                stored_frame_dir=root / "frames",
            )

            self.assertTrue(deleted)
            self.assertIsNone(main.fetch_analysis_detail("analysis-1", db_path))
            self.assertFalse(video_path.exists())
            self.assertFalse(frame_dir.exists())

    def test_create_and_update_analysis_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analysis.db"
            main.init_db(db_path)
            job_id = main.create_analysis_job("large-demo.mp4", "gemini-2.5-pro", db_path=db_path)

            queued = main.get_analysis_job(job_id, db_path=db_path)
            self.assertEqual(queued["status"], "queued")
            self.assertEqual(queued["filename"], "large-demo.mp4")

            updated = main.update_analysis_job(
                job_id,
                status="completed",
                analysis_id="analysis-1",
                video_url="/storage/videos/demo.mp4",
                db_path=db_path,
            )
            self.assertEqual(updated["status"], "completed")
            self.assertEqual(main.get_analysis_job(job_id, db_path=db_path)["analysis_id"], "analysis-1")

    def test_download_video_from_url_requires_ytdlp(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(main, "yt_dlp", None):
            with self.assertRaises(main.VideoDownloadError) as ctx:
                main.download_video_from_url("https://www.youtube.com/watch?v=demo", Path(tmp))

        self.assertIn("手动上传视频文件", str(ctx.exception))

    def test_download_video_from_url_maps_downloader_error_to_manual_upload_hint(self):
        class FailingYoutubeDL:
            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, *_args, **_kwargs):
                raise RuntimeError("HTTP Error 403: Forbidden")

        fake_ytdlp = Mock()
        fake_ytdlp.YoutubeDL = FailingYoutubeDL

        with tempfile.TemporaryDirectory() as tmp, patch.object(main, "yt_dlp", fake_ytdlp):
            with self.assertRaises(main.VideoDownloadError) as ctx:
                main.download_video_from_url("https://www.tiktok.com/@demo/video/1", Path(tmp))

        message = str(ctx.exception)
        self.assertIn("平台拒绝下载请求", message)
        self.assertIn("手动上传", message)

    def test_persist_job_preview_video_copies_downloaded_video_for_polling_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded.mp4"
            stored_dir = root / "stored"
            source.write_bytes(b"video bytes")
            stored_dir.mkdir()

            with patch.object(main, "STORED_VIDEO_DIR", stored_dir):
                preview_url = main.persist_job_preview_video("job-1", source, "demo video.mp4")

            self.assertEqual(preview_url, "/storage/videos/job_job-1_demo_video.mp4")
            self.assertEqual((stored_dir / "job_job-1_demo_video.mp4").read_bytes(), b"video bytes")

    def test_get_analysis_job_by_analysis_id_prefers_active_reanalysis_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analysis.db"
            main.init_db(db_path)
            completed_job_id = main.create_analysis_job("demo.mp4", "gpt-4o", db_path=db_path)
            main.update_analysis_job(completed_job_id, status="completed", analysis_id="analysis-1", db_path=db_path)
            active_job_id = main.create_analysis_job("demo.mp4", "gemini-2.5-pro", db_path=db_path)
            main.update_analysis_job(
                active_job_id,
                status="processing",
                replace_analysis_id="analysis-1",
                db_path=db_path,
            )

            job = main.get_analysis_job_by_analysis_id("analysis-1", db_path=db_path)

            self.assertEqual(job["job_id"], active_job_id)
            self.assertEqual(job["status"], "processing")

    def test_run_analysis_pipeline_rejects_empty_storyboard_result(self):
        with patch.object(main, "extract_frames"), \
             patch.object(main, "extract_audio", return_value=False), \
             patch.object(main, "sample_visual_frames", return_value=[]), \
             patch.object(main, "build_analysis_prompt", return_value="PROMPT"), \
             patch.object(main, "print_final_prompt_for_debug"), \
             patch.object(main, "analyze_video", return_value="[]"), \
             patch.object(main, "persist_analysis") as persist:
            with self.assertRaisesRegex(RuntimeError, "未生成有效分镜"):
                main.run_analysis_pipeline("/tmp/demo.mp4", "demo.mp4", "gemini-2.5-pro")

        persist.assert_not_called()

    def test_run_analysis_pipeline_logs_audio_and_subtitle_timing_before_ai_analysis(self):
        result = json.dumps([{"title": "开场", "start_time": 0, "end_time": 1}], ensure_ascii=False)
        with patch.object(main, "extract_frames"), \
             patch.object(main, "extract_audio", return_value=True), \
             patch.object(main, "audio_to_text", return_value="TRANSCRIPT"), \
             patch.object(main, "sample_visual_frames", return_value=[]), \
             patch.object(main, "build_analysis_prompt", return_value="PROMPT"), \
             patch.object(main, "print_final_prompt_for_debug"), \
             patch.object(main, "analyze_video", return_value=result), \
             patch.object(main, "enrich_storyboard_result", return_value=result), \
             patch.object(main, "persist_analysis", return_value={"analysis_id": "analysis-1", "video_url": "", "data": []}), \
             patch.object(main, "log_analysis_job") as log_job:
            main.run_analysis_pipeline("/tmp/demo.mp4", "demo.mp4", "gemini-2.5-pro", job_id="job-1")

        messages = [call.args[1] for call in log_job.call_args_list]
        timing_index = messages.index("音频和字幕耗时统计")
        ai_index = messages.index("开始调用 AI 分析")
        self.assertLess(timing_index, ai_index)

        timing_kwargs = log_job.call_args_list[timing_index].kwargs
        self.assertRegex(timing_kwargs["video_to_audio"], r"^\d+\.\d{2}s$")
        self.assertRegex(timing_kwargs["subtitle_analysis"], r"^\d+\.\d{2}s$")

    def test_run_analysis_pipeline_uses_manual_transcript_without_asr(self):
        result = json.dumps([{"title": "开场", "start_time": 0, "end_time": 1}], ensure_ascii=False)
        manual_transcript = "0.00 --> 3.08 Rule number one, read the reviews."
        with patch.object(main, "extract_frames"), \
             patch.object(main, "extract_audio") as extract_audio, \
             patch.object(main, "audio_to_text") as audio_to_text, \
             patch.object(main, "sample_visual_frames", return_value=[]), \
             patch.object(main, "build_analysis_prompt", return_value="PROMPT") as build_prompt, \
             patch.object(main, "print_final_prompt_for_debug"), \
             patch.object(main, "analyze_video", return_value=result), \
             patch.object(main, "enrich_storyboard_result", return_value=result), \
             patch.object(main, "persist_analysis", return_value={"analysis_id": "analysis-1", "video_url": "", "data": []}), \
             patch.object(main, "log_analysis_job") as log_job:
            main.run_analysis_pipeline(
                "/tmp/demo.mp4",
                "demo.mp4",
                "gemini-2.5-pro",
                job_id="job-1",
                transcript_override=manual_transcript,
            )

        extract_audio.assert_not_called()
        audio_to_text.assert_not_called()
        build_prompt.assert_called_once_with(manual_transcript, [])
        self.assertIn("使用手动字幕，跳过音频提取和 ASR", [call.args[1] for call in log_job.call_args_list])

    def test_run_analysis_pipeline_uses_empty_transcript_when_asr_fails(self):
        result = json.dumps([{"title": "寮€鍦?", "start_time": 0, "end_time": 1}], ensure_ascii=False)
        with patch.object(main, "extract_frames"), \
             patch.object(main, "extract_audio", return_value=True), \
             patch.object(main, "audio_to_text", side_effect=RuntimeError("asr crashed")) as audio_to_text, \
             patch.object(main, "sample_visual_frames", return_value=[]), \
             patch.object(main, "build_analysis_prompt", return_value="PROMPT") as build_prompt, \
             patch.object(main, "print_final_prompt_for_debug"), \
             patch.object(main, "analyze_video", return_value=result), \
             patch.object(main, "enrich_storyboard_result", return_value=result), \
             patch.object(main, "persist_analysis", return_value={"analysis_id": "analysis-1", "video_url": "", "data": []}):
            main.run_analysis_pipeline("/tmp/demo.mp4", "demo.mp4", "gemini-2.5-pro", job_id="job-1")

        audio_to_text.assert_called_once()
        build_prompt.assert_called_once_with("", [])

    def test_audio_to_text_returns_empty_when_asr_is_disabled(self):
        with patch.object(main, "ENABLE_ASR", False), \
             patch.object(main, "get_faster_whisper_model") as faster_model, \
             patch.object(main, "get_whisper_model") as whisper_model:
            self.assertEqual(main.audio_to_text(), "")

        faster_model.assert_not_called()
        whisper_model.assert_not_called()

    def test_cancel_analysis_job_marks_job_canceled_and_hides_internal_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analysis.db"
            main.init_db(db_path)
            job_id = main.create_analysis_job("large-demo.mp4", "gemini-2.5-pro", db_path=db_path)

            canceled = main.cancel_analysis_job(job_id, db_path=db_path)

            self.assertEqual(canceled["status"], "canceled")
            self.assertTrue(canceled["cancel_requested"])
            self.assertNotIn("_cancel_event", canceled)
            self.assertNotIn("_cancel_event", main.get_analysis_job(job_id, db_path=db_path))

    def test_canceled_analysis_job_is_not_overwritten_by_late_processing_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analysis.db"
            main.init_db(db_path)
            job_id = main.create_analysis_job("large-demo.mp4", "gemini-2.5-pro", db_path=db_path)
            main.cancel_analysis_job(job_id, db_path=db_path)

            updated = main.update_analysis_job(job_id, status="processing", message="late update", db_path=db_path)

            self.assertEqual(updated["status"], "canceled")
            self.assertEqual(main.get_analysis_job(job_id, db_path=db_path)["status"], "canceled")

    def test_prepare_reanalysis_job_copies_saved_video_to_isolated_job_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "analysis.db"
            saved_video = root / "saved" / "demo.mp4"
            saved_video.parent.mkdir()
            saved_video.write_bytes(b"fake video bytes")
            job_dir = root / "jobs"
            main.init_db(db_path)
            main.save_analysis_record(
                {
                    "id": "analysis-1",
                    "filename": "demo.mp4",
                    "model": "gemini-2.5-pro",
                    "video_path": str(saved_video),
                    "video_url": "/storage/videos/demo.mp4",
                    "result_json": "[]",
                    "formula": "",
                    "subtype": "",
                    "category_reason": "",
                    "created_at": "2026-05-11T10:00:00+08:00",
                },
                db_path,
            )

            prepared = main.prepare_reanalysis_job(
                "analysis-1",
                model="gpt4o",
                db_path=db_path,
                job_upload_dir=job_dir,
            )

            copied_path = Path(prepared["video_path"])
            self.assertEqual(prepared["filename"], "demo.mp4")
            self.assertEqual(prepared["model"], "gpt4o")
            self.assertNotEqual(copied_path.parent, saved_video.parent)
            self.assertEqual(copied_path.read_bytes(), b"fake video bytes")
            self.assertEqual(main.get_analysis_job(prepared["job_id"])["status"], "queued")
            self.assertEqual(main.get_analysis_job(prepared["job_id"])["replace_analysis_id"], "analysis-1")

    def test_enrich_reclassifies_dupe_comparison_as_alternative_showdown(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 6,
                "title": "产品差异",
                "scene_description": "创作者抛出 Which is better 的选择问题，把贵价品牌和更便宜的 dupe 放在同一段比较。",
                "script": "Which is better, the expensive one or this cheaper dupe?",
                "viral_formula": "分屏对比",
                "formula_subtype": "前后分屏型",
                "category_reason": "模型误判为前后效果变化。",
            },
            {
                "start_time": 6,
                "end_time": 12,
                "title": "优惠活动",
                "scene_description": "继续强调 cheaper、save money 和替代购买方案。",
                "script": "This one is way cheaper and works as an alternative.",
                "viral_formula": "分屏对比",
                "formula_subtype": "前后分屏型",
                "category_reason": "模型误判为前后效果变化。",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertTrue(all(item["formula_subtype"] == "平替对决型" for item in enriched))
        self.assertTrue(all(item["viral_formula"] == "分屏对比" for item in enriched))
        self.assertIn("平替", enriched[0]["category_reason"])

    def test_enrich_reclassifies_price_per_serving_comparison_as_alternative_showdown(self):
        model_result = json.dumps([
            {
                "start_time": 0.5,
                "end_time": 1.7,
                "title": "产品差异",
                "scene_description": "桌面上并列展示 Vita Coco 和 D-BLOAT，并用 Which is better 建立选择悬念。",
                "script": "Vita Coco vs D-BLOAT. Which is better?",
                "viral_formula": "分屏对比",
                "formula_subtype": "前后分屏型",
                "category_reason": "画面中对比两种产品。",
            },
            {
                "start_time": 2.8,
                "end_time": 5.1,
                "title": "价格促销",
                "scene_description": "画面用每份 $3 和每份 $1 对比两种产品的价格优势。",
                "script": "$3 per serving $1 per serving",
                "viral_formula": "分屏对比",
                "formula_subtype": "前后分屏型",
                "category_reason": "价格对比出现在画面中。",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertTrue(all(item["formula_subtype"] == "平替对决型" for item in enriched))

    def test_enrich_reclassifies_first_person_competitor_price_comparison_as_alternative_showdown(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 3,
                "title": "故事开场",
                "scene_description": "第一人称手持蒸汽清洁器清理水垢，字幕提示 Learn from my mistakes。",
                "script": "Rule number one, you should always read the reviews when it comes to TikTok, because",
                "viral_formula": "第一人称视角",
                "formula_subtype": "困境解决型",
                "category_reason": "模型误判为第一人称清洁困境。",
            },
            {
                "start_time": 3,
                "end_time": 10,
                "title": "产品差异",
                "scene_description": "口播明确把 viral red-hut steam cleaner 和 220 美元的 Bissell steam shot 进行对比。",
                "script": "like you, I bought the viral red-hut steam cleaner and compared it next to my $220 Bissell steam shot, and now I actually have to return it.",
                "viral_formula": "第一人称视角",
                "formula_subtype": "困境解决型",
                "category_reason": "模型误判为第一人称清洁困境。",
            },
            {
                "start_time": 27,
                "end_time": 34,
                "title": "价格促销",
                "scene_description": "画面展示实体店 120 美元和 TikTok Shop 大促价格之间的价格差。",
                "script": "But I'm actually returning mine because I didn't get it off TikTok, and I paid $120 for it in store, and TikTok just went and put it on a huge sale.",
                "viral_formula": "第一人称视角",
                "formula_subtype": "困境解决型",
                "category_reason": "模型误判为第一人称清洁困境。",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertTrue(all(item["viral_formula"] == "分屏对比" for item in enriched))
        self.assertTrue(all(item["formula_subtype"] == "平替对决型" for item in enriched))
        self.assertIn("平替", enriched[0]["category_reason"])

    def test_enrich_keeps_unboxing_haul_with_sale_tip_as_unboxing_review(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 7,
                "title": "故事开场",
                "scene_description": "创作者拿着巨大的黑色包裹并揭示来自 ComfortBitch，邀请观众一起打开。",
                "script": "Holy shit! Look how big this package is! It's from ComfortBitch. Let's open it together.",
                "viral_formula": "分屏对比",
                "formula_subtype": "平替对决型",
                "category_reason": "模型误把价格技巧当作全片对比结构。",
            },
            {
                "start_time": 13,
                "end_time": 28,
                "title": "优惠活动",
                "scene_description": "创作者拆开包裹，说明买了童码并提到 on sale 和 way cheaper 的购买技巧。",
                "script": "Let's open this. They were on sale and I got the kid sizes. You get the kid sizes if you can fit in it. And it's way cheaper.",
                "viral_formula": "分屏对比",
                "formula_subtype": "平替对决型",
                "category_reason": "模型误把价格技巧当作全片对比结构。",
            },
            {
                "start_time": 63,
                "end_time": 99,
                "title": "真实体验",
                "scene_description": "创作者试穿整套扎染服装，评价很柔软并建议促销时购买。",
                "script": "Oh my god, this is so cute. I'm obsessed. It is so freaking soft. Get it when it's on sale.",
                "viral_formula": "分屏对比",
                "formula_subtype": "平替对决型",
                "category_reason": "模型误把价格技巧当作全片对比结构。",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertTrue(all(item["viral_formula"] == "开箱 / ASMR" for item in enriched))
        self.assertTrue(all(item["formula_subtype"] == "开箱评测型" for item in enriched))
        self.assertIn("开箱", enriched[0]["category_reason"])

    def test_enrich_keeps_single_brand_size_and_sale_haul_as_unboxing_review(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 13,
                "title": "故事开场",
                "scene_description": "创作者展示巨大包裹并提到 ComfortBitch，随后先喝饮料制造生活化开场。",
                "script": "Holy shit, this is huge. It's from ComfortBitch.",
                "viral_formula": "分屏对比",
                "formula_subtype": "平替对决型",
                "category_reason": "模型误把尺码讨论当作对比。",
            },
            {
                "start_time": 13,
                "end_time": 38,
                "title": "优惠活动",
                "scene_description": "创作者说明这次购买同一品牌的童码、成人码和扎染款，因为打折且童码更便宜。",
                "script": "They were on sale and I got the kid sizes. You get the kid sizes if you can fit in it. And it's way cheaper. I've been wanting the tie-dye.",
                "viral_formula": "分屏对比",
                "formula_subtype": "平替对决型",
                "category_reason": "模型误把尺码讨论当作对比。",
            },
            {
                "start_time": 38,
                "end_time": 99,
                "title": "真实体验",
                "scene_description": "创作者连续展示同一品牌的紫色和粉色运动裤、连帽衫，并试穿评价尺码和柔软度。",
                "script": "I got the hoodie too. I got the pink too. Let me try them on. I don't like the kid sizes. It is so freaking soft.",
                "viral_formula": "分屏对比",
                "formula_subtype": "平替对决型",
                "category_reason": "模型误把尺码讨论当作对比。",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertTrue(all(item["viral_formula"] == "开箱 / ASMR" for item in enriched))
        self.assertTrue(all(item["formula_subtype"] == "开箱评测型" for item in enriched))
        self.assertIn("开箱", enriched[0]["category_reason"])

    def test_analysis_prompt_requires_stage_based_storyboard_detail(self):
        prompt = main.build_analysis_prompt(
            transcript="00:00 --> 00:06 Which is better, the expensive one or this cheaper dupe?",
            visual_frames=[{"id": "F01", "timestamp": 1.2, "data_url": "data:image/jpeg;base64,abc"}],
        )

        self.assertIn("明确双对象/双方案对比", prompt)
        self.assertIn("开箱主导结构优先归为开箱 / ASMR", prompt)
        self.assertIn("视觉场景切换", prompt)
        self.assertIn("单个分镜时长不得超过 12 秒", prompt)
        self.assertIn("分镜数量要克制", prompt)
        self.assertIn("产品对比", prompt)
        self.assertIn("如果已经形成明确双对象比较，优先用“产品对比”", prompt)
        self.assertIn("多个连续片段都在围绕同一产品", prompt)
        self.assertIn("scene_description 至少 30 个中文字符", prompt)
        self.assertIn("script 需要覆盖该段完整口播/字幕语义", prompt)
        self.assertIn("无有效口播/字幕", prompt)
        self.assertIn("不要把一句完整台词、因果句、转折句或从句拆到两个分镜里", prompt)
        self.assertIn("分镜时间边界可以围绕视觉切点前后微调", prompt)
        self.assertIn("卖点角度分类体系", prompt)
        self.assertIn("黄金3秒钩子分类体系", prompt)
        self.assertIn('"selling_point_angle"', prompt)
        self.assertIn('"golden_3s_hook"', prompt)
        self.assertIn("没有明确命中黄金3秒钩子时", prompt)
        self.assertIn("12-30 秒的镜前 GRWM POV", prompt)
        self.assertIn("通常拆成 3-4 个分镜", prompt)
        self.assertIn("GRWM + 产品 / 仪式步骤型", prompt)
        self.assertIn("护肤/护发/美妆/洗护 GRWM", prompt)
        self.assertIn("使用频率/适用状态", prompt)
        self.assertIn("开头的夸张情绪宣言", prompt)

    def test_normalizes_comparison_story_step_to_product_comparison(self):
        item = {
            "title": "对比展示",
            "content_tag": "竞品比较",
            "scene_description": "画面把 Redhut 和 Bissell 两个蒸汽清洁器放在一起比较。",
            "script": "Which is better? I compared it next to my Bissell steam shot.",
        }

        main.normalize_content_tag(item)
        main.normalize_story_step_labels(item)

        self.assertEqual(item["title"], "产品对比")
        self.assertEqual(item["content_tag"], "产品对比")

    def test_enrich_normalizes_mirror_grwm_tryon_to_ritual_steps(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 18,
                "title": "服装试穿与展示",
                "scene_description": "创作者站在穿衣镜前对镜自拍，穿着浅蓝色牛仔裤，从正面、侧面和背面转身展示版型、腰部贴合和臀部线条，并提到尺码和购买链接。",
                "script": "画面/字幕摘要: mirror GRWM try on jeans, showing the fit, wash, sizing and code.",
                "product_category": "服饰",
                "content_tag": "真实体验",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "穿搭展示型",
                "category_reason": "整个视频围绕产品试穿和镜中展示展开。",
            }
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertEqual(enriched[0]["viral_formula"], "GRWM + 产品")
        self.assertEqual(enriched[0]["formula_subtype"], "仪式步骤型")
        self.assertIn("镜前 GRWM POV", enriched[0]["category_reason"])

    def test_enrich_normalizes_haircare_grwm_instruction_to_ritual_steps(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 3,
                "title": "情绪营销",
                "scene_description": "创作者在卧室展示浓密卷发，用夸张情绪钩子表达自己离不开这款头皮按摩喷雾。",
                "script": "Prefiero cambiar de marido antes que dejar de usarlo.",
                "product_category": "护发",
                "content_tag": "情绪营销",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "情感叙事型",
                "category_reason": "开头用强烈情感宣言驱动产品出现。",
            },
            {
                "start_time": 3,
                "end_time": 15,
                "title": "使用说明",
                "scene_description": "画面切到产品特写和头皮护理场景，字幕按照头发干枯、掉发严重、头皮明显三种状态说明不同使用频率，并要求用手指按摩发根。",
                "script": "Si tu cabello está seco o dañado, usa lo cada tres días. Si la caída es fuerte, usa lo cada dos días. Si ya se ve claramente el cuero cabelludo, usalo a, diario. Masajea con los dedos para nutrir profundamente la raíz.",
                "product_category": "护发",
                "content_tag": "使用说明",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "情感叙事型",
                "category_reason": "模型误把开头情绪钩子当作全片小类。",
            },
            {
                "start_time": 15,
                "end_time": 27,
                "title": "产品功效",
                "scene_description": "视频展示 minoxidil、jengibre 和 keratina 成分，随后呈现按摩后头皮放松、买一送一优惠和复购理由。",
                "script": "Con ingredientes suaves, minoxidil, jengibre y keratina, apto para hombres y mujeres. Después del masaje, el cuero cabelludo se siente muy relajado. Ahora está en promoción de compra 1 y llevate 1 gratis.",
                "product_category": "护发",
                "content_tag": "产品功效",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "情感叙事型",
                "category_reason": "模型误把开头情绪钩子当作全片小类。",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/haircare.mp4"))

        self.assertTrue(all(item["viral_formula"] == "GRWM + 产品" for item in enriched))
        self.assertTrue(all(item["formula_subtype"] == "仪式步骤型" for item in enriched))
        self.assertIn("使用频率", enriched[0]["category_reason"])
        self.assertIn("情绪钩子", enriched[0]["category_reason"])

    def test_enrich_reclassifies_miraj_haircare_pov_as_grwm_product(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 6,
                "title": "用户痛点",
                "scene_description": "浴室镜头中男子展示头发稀疏和发际线问题，画面叠字为 POV: The anti baldness solution，建立防脱发护理需求。",
                "script": "POV: The anti baldness solution",
                "product_category": "护发",
                "content_tag": "用户痛点",
                "viral_formula": "分屏对比",
                "formula_subtype": "方法对比型",
                "category_reason": "模型误把前后效果当成方法对比。",
            },
            {
                "start_time": 6,
                "end_time": 12,
                "title": "产品亮相",
                "scene_description": "男子拿出 MIRAJ 品牌黑色 ANTI-DHT SHAMPOO 和白色瓶装产品，随后用刷子涂抹黑色膏体并清洗起泡。",
                "script": "无有效口播/字幕",
                "product_category": "护发",
                "content_tag": "产品亮相",
                "viral_formula": "第一人称视角",
                "formula_subtype": "过程演示型",
                "category_reason": "模型误把 POV 文案当作第一人称主类。",
            },
            {
                "start_time": 12,
                "end_time": 18,
                "title": "产品功效",
                "scene_description": "最后展示使用后头顶覆盖和发量观感效果，强调 anti baldness solution 的最终结果。",
                "script": "无有效口播/字幕",
                "product_category": "护发",
                "content_tag": "产品功效",
                "viral_formula": "分屏对比",
                "formula_subtype": "前后分屏型",
                "category_reason": "模型误把前后变化当成分屏对比。",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/miraj.mp4"))

        self.assertTrue(all(item["viral_formula"] == "GRWM + 产品" for item in enriched))
        self.assertTrue(all(item["formula_subtype"] == "仪式步骤型" for item in enriched))
        self.assertIn("POV 文案", enriched[0]["category_reason"])

    def test_enrich_does_not_mark_same_item_color_split_as_alternative_or_before_after(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 2,
                "title": "产品信息",
                "scene_description": "年轻女士身着粉色长袍 abaya 在客厅全身展示，露出柔和色调和垂坠感。",
                "script": "无有效口播/字幕",
                "product_category": "服装",
                "content_tag": "产品信息",
                "viral_formula": "分屏对比",
                "formula_subtype": "平替对决型",
                "category_reason": "模型误把不同颜色当成平替。",
            },
            {
                "start_time": 2,
                "end_time": 4,
                "title": "产品差异",
                "scene_description": "画面切换为左右分屏，同款长袍分别展示粉色和灰色，突出不同颜色和姿态差异。",
                "script": "无有效口播/字幕",
                "product_category": "服装",
                "content_tag": "产品差异",
                "viral_formula": "分屏对比",
                "formula_subtype": "前后分屏型",
                "category_reason": "模型误把同款颜色分屏当成使用前后。",
            },
            {
                "start_time": 4,
                "end_time": 7,
                "title": "产品信息",
                "scene_description": "女士继续穿灰色长袍微笑展示动态姿态，画面延续同款服装的颜色和上身观感展示。",
                "script": "无有效口播/字幕",
                "product_category": "服装",
                "content_tag": "产品信息",
                "viral_formula": "分屏对比",
                "formula_subtype": "平替对决型",
                "category_reason": "模型误把同款不同色当成平替对决。",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/abaya.mp4"))

        self.assertTrue(all(item["viral_formula"] == "分屏对比" for item in enriched))
        self.assertTrue(all(item["formula_subtype"] == "产品对比型" for item in enriched))
        self.assertIn("不同颜色", enriched[0]["category_reason"])
        self.assertNotIn("平替", enriched[0]["formula_subtype"])
        self.assertNotIn("前后", enriched[0]["formula_subtype"])

    def test_enrich_reclassifies_abaya_grwm_split_to_split_product_comparison(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 2,
                "title": "产品信息",
                "scene_description": "女性身穿粉色长款连衣裙和配套头巾站在室内展示，画面重点是同款服装的上身效果和整体垂坠感。",
                "script": "无有效口播/字幕",
                "product_category": "服装",
                "content_tag": "产品信息",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "仪式步骤型",
                "category_reason": "模型误把服装展示当成 GRWM 准备流程。",
            },
            {
                "start_time": 2,
                "end_time": 4,
                "title": "产品对比",
                "scene_description": "同一位女性穿同款但为灰色的长款连衣裙，画面通过左右分屏和快速切换对照粉色与灰色两种颜色。",
                "script": "无有效口播/字幕",
                "product_category": "服装",
                "content_tag": "产品对比",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "仪式步骤型",
                "category_reason": "模型误把同款不同颜色对照当作仪式步骤。",
            },
            {
                "start_time": 4,
                "end_time": 8,
                "title": "产品差异",
                "scene_description": "粉色与灰色两款同款 abaya 上身效果通过快速交叉剪辑呈现，突出不同颜色和姿态的视觉差异。",
                "script": "无有效口播/字幕",
                "product_category": "服装",
                "content_tag": "产品差异",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "仪式步骤型",
                "category_reason": "模型未识别这是同款商品变体对照。",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/abaya.mp4"))

        self.assertTrue(all(item["viral_formula"] == "分屏对比" for item in enriched))
        self.assertTrue(all(item["formula_subtype"] == "产品对比型" for item in enriched))
        self.assertIn("分屏对照展示", enriched[0]["category_reason"])

    def test_enrich_adds_selling_point_and_golden_3s_taxonomy(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 3,
                "title": "用户痛点",
                "scene_description": "画面聚焦地板和墙角大量宠物毛发，字幕用 Got shedding pets? 直接提问。",
                "script": "Got shedding pets? listen if your house is a zoo with pet hair like mine.",
                "viral_formula": "第一人称视角",
                "formula_subtype": "困境解决型",
            },
            {
                "start_time": 3,
                "end_time": 12,
                "title": "产品功效",
                "scene_description": "空气净化器被放在毛发环境里，口播强调会把漂浮毛发捕捉住。",
                "script": "this purifier will capture hair at a thin air.",
                "viral_formula": "第一人称视角",
                "formula_subtype": "困境解决型",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertTrue(all(item["selling_point_angle"] == "展示效果" for item in enriched))
        self.assertTrue(all(item["selling_point_subtype"] == "实时演示" for item in enriched))
        self.assertTrue(all(item["golden_3s_hook"] == "提问式" for item in enriched))
        self.assertTrue(all(item["golden_3s_subtype"] == "痛点提问" for item in enriched))

    def test_enrich_leaves_golden_3s_empty_when_opening_has_no_clear_hook(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 5,
                "title": "场景设定",
                "scene_description": "创作者站在卧室镜子前整理衣服，画面自然展示一件日常穿搭单品。",
                "script": "Today I'm getting ready and showing this outfit.",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "场景驱动型",
            },
            {
                "start_time": 5,
                "end_time": 18,
                "title": "产品卖点",
                "scene_description": "创作者转身展示上身效果和整体版型，强调日常穿搭的舒适和审美风格。",
                "script": "It is so comfy and goes with everything.",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "场景驱动型",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertTrue(all(item["selling_point_angle"] for item in enriched))
        self.assertTrue(all(item["selling_point_subtype"] for item in enriched))
        self.assertTrue(all(item["golden_3s_hook"] == "" for item in enriched))
        self.assertTrue(all(item["golden_3s_subtype"] == "" for item in enriched))
        self.assertTrue(all(item["golden_3s_reason"] == "" for item in enriched))

    def test_enrich_prefers_price_advantage_for_plain_sale_announcement_without_golden_3s(self):
        model_result = json.dumps([
            {
                "start_time": 0,
                "end_time": 4,
                "title": "故事开场",
                "scene_description": "创作者站在卧室镜子前自拍展示牛仔裤，并说自己赶来告诉大家这次 sale 消息。",
                "script": "Never say I never did anything for you because I literally ran on here to tell you guys about this sale.",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "仪式步骤型",
                "selling_point_angle": "制造紧迫感",
                "selling_point_subtype": "限时折扣",
                "golden_3s_hook": "秘诀/技巧",
                "golden_3s_subtype": "省钱秘笈",
                "golden_3s_reason": "模型把普通 sale 通知误判为省钱技巧钩子。",
            },
            {
                "start_time": 4,
                "end_time": 11,
                "title": "价格促销",
                "scene_description": "创作者转身展示牛仔裤版型，同时强调这条 best selling style 平时从不打折，总是收全价。",
                "script": "These jeans are absolutely never on sale. They're one of Pacsun's best selling style. So they're always charging full price, look at the price of these bad boys right now.",
                "viral_formula": "GRWM + 产品",
                "formula_subtype": "仪式步骤型",
                "selling_point_angle": "制造紧迫感",
                "selling_point_subtype": "限时折扣",
                "golden_3s_hook": "秘诀/技巧",
                "golden_3s_subtype": "省钱秘笈",
            },
        ], ensure_ascii=False)

        with patch("backend.main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/pacsun.mp4"))

        self.assertTrue(all(item["selling_point_angle"] == "价格优势" for item in enriched))
        self.assertTrue(all(item["selling_point_subtype"] == "直接比价" for item in enriched))
        self.assertTrue(all(item["golden_3s_hook"] == "" for item in enriched))
        self.assertTrue(all(item["golden_3s_subtype"] == "" for item in enriched))


if __name__ == "__main__":
    unittest.main()
