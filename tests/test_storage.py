import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class AnalysisStorageTest(unittest.TestCase):
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

            detail = main.fetch_analysis_detail("analysis-1", db_path)
            self.assertEqual(detail["filename"], "demo.mp4")
            self.assertEqual(detail["data"][0]["formula_subtype"], "前后分屏型")

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
            self.assertEqual(detail["data"][0]["image_url"], "/storage/frames/analysis-1/shot_01.jpg")
            self.assertEqual((stored_frames / "analysis-1" / "shot_01.jpg").read_bytes(), b"new frame")

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
        job_id = main.create_analysis_job("large-demo.mp4", "gemini-2.5-pro")

        queued = main.get_analysis_job(job_id)
        self.assertEqual(queued["status"], "queued")
        self.assertEqual(queued["filename"], "large-demo.mp4")

        updated = main.update_analysis_job(
            job_id,
            status="completed",
            analysis_id="analysis-1",
            video_url="/storage/videos/demo.mp4",
        )
        self.assertEqual(updated["status"], "completed")
        self.assertEqual(main.get_analysis_job(job_id)["analysis_id"], "analysis-1")

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

        with patch("main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
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

        with patch("main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertTrue(all(item["formula_subtype"] == "平替对决型" for item in enriched))

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

        with patch("main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertTrue(all(item["viral_formula"] == "开箱 / ASMR" for item in enriched))
        self.assertTrue(all(item["formula_subtype"] == "开箱评测型" for item in enriched))
        self.assertIn("开箱", enriched[0]["category_reason"])

    def test_analysis_prompt_requires_fine_grained_storyboard_detail(self):
        prompt = main.build_analysis_prompt(
            transcript="00:00 --> 00:06 Which is better, the expensive one or this cheaper dupe?",
            visual_frames=[{"id": "F01", "timestamp": 1.2, "data_url": "data:image/jpeg;base64,abc"}],
        )

        self.assertIn("明确双对象/双方案对比", prompt)
        self.assertIn("开箱主导结构优先归为开箱 / ASMR", prompt)
        self.assertIn("scene_description 至少 30 个中文字符", prompt)
        self.assertIn("script 需要覆盖该段完整语义", prompt)


if __name__ == "__main__":
    unittest.main()
