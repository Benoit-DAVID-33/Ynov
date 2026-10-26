from app.store import JobStore


def _job(store, tmp_path, job_id, fmt):
    store.create(job_id, f"{job_id}.wav", "audio", tmp_path / "x.wav")
    store.queue(job_id, fmt)


def test_stats(tmp_path):
    store = JobStore(tmp_path / "db.sqlite")
    _job(store, tmp_path, "a", "text")
    _job(store, tmp_path, "b", "subtitles")
    _job(store, tmp_path, "c", "subtitles")
    _job(store, tmp_path, "d", "text")
    store.mark_done("a", tmp_path / "r.txt", "hello", media_seconds=10, processing_seconds=2)
    store.mark_done("b", tmp_path / "r.srt", "hi", media_seconds=10, processing_seconds=4)
    store.mark_failed("c", "boom")
    store.mark_processing("d")

    stats = store.stats()
    assert stats["inferences_done"] == 2
    assert stats["inferences_done_by_type"] == {"text": 1, "subtitles": 1}
    assert stats["avg_processing_seconds"] == 3
    assert stats["avg_realtime_factor"] == 0.3
    assert stats["failed"] == 1 and stats["failed_by_type"] == {"subtitles": 1}
    assert stats["unfinished"] == 1 and stats["unfinished_by_type"] == {"text": 1}
    assert [j["id"] for j in store.list_unfinished()] == ["d"]
    assert {r["result_text"] for r in store.list_responses()} == {"hello", "hi"}
