import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import main


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
             patch("main.requests.post", return_value=response) as post:
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
             patch("main.requests.post", return_value=response) as post:
            result = main.analyze_video("TRANSCRIPT", "gemini-2.5-pro", "/tmp/demo.mp4")

        self.assertEqual(result, '[{"title":"故事开场"}]')
        payload = post.call_args.kwargs["json"]
        self.assertEqual(post.call_args.args[0], "https://gptproto.com/v1/chat/completions")
        self.assertEqual(payload["model"], "gemini-2.5-pro")

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
        self.assertEqual(values, ["gemini-2.5-pro", "gpt-4o"])
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

    def test_cancel_analysis_job_marks_job_canceled_and_hides_internal_event(self):
        job_id = main.create_analysis_job("large-demo.mp4", "gemini-2.5-pro")

        canceled = main.cancel_analysis_job(job_id)

        self.assertEqual(canceled["status"], "canceled")
        self.assertTrue(canceled["cancel_requested"])
        self.assertNotIn("_cancel_event", canceled)
        self.assertNotIn("_cancel_event", main.get_analysis_job(job_id))

    def test_canceled_analysis_job_is_not_overwritten_by_late_processing_update(self):
        job_id = main.create_analysis_job("large-demo.mp4", "gemini-2.5-pro")
        main.cancel_analysis_job(job_id)

        updated = main.update_analysis_job(job_id, status="processing", message="late update")

        self.assertEqual(updated["status"], "canceled")
        self.assertEqual(main.get_analysis_job(job_id)["status"], "canceled")

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

        with patch("main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
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
        self.assertIn("阶段化分镜拆解", prompt)
        self.assertIn("5-8 个分镜", prompt)
        self.assertIn("不要逐句切分", prompt)
        self.assertIn("scene_description 至少 30 个中文字符", prompt)
        self.assertIn("script 需要覆盖该段完整语义", prompt)
        self.assertIn("卖点角度分类体系", prompt)
        self.assertIn("黄金3秒钩子分类体系", prompt)
        self.assertIn('"selling_point_angle"', prompt)
        self.assertIn('"golden_3s_hook"', prompt)
        self.assertIn("没有明确命中黄金3秒钩子时", prompt)
        self.assertIn("12-30 秒的镜前 GRWM POV", prompt)
        self.assertIn("通常拆成 3-4 个分镜", prompt)
        self.assertIn("GRWM + 产品 / 仪式步骤型", prompt)

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

        with patch("main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertEqual(enriched[0]["viral_formula"], "GRWM + 产品")
        self.assertEqual(enriched[0]["formula_subtype"], "仪式步骤型")
        self.assertIn("镜前 GRWM POV", enriched[0]["category_reason"])

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

        with patch("main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
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

        with patch("main.extract_storyboard_images", side_effect=lambda _video_path, items: items):
            enriched = json.loads(main.enrich_storyboard_result(model_result, "/tmp/not-a-real-video.mp4"))

        self.assertTrue(all(item["selling_point_angle"] for item in enriched))
        self.assertTrue(all(item["selling_point_subtype"] for item in enriched))
        self.assertTrue(all(item["golden_3s_hook"] == "" for item in enriched))
        self.assertTrue(all(item["golden_3s_subtype"] == "" for item in enriched))
        self.assertTrue(all(item["golden_3s_reason"] == "" for item in enriched))


if __name__ == "__main__":
    unittest.main()
