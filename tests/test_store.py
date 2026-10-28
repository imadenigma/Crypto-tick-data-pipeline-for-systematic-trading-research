import pandas as pd

from orderflow.data.store import interim_path, read_meta, write_interim


def _frame():
    return pd.DataFrame({"ts": [1_722_816_000_000_000, 1_722_816_000_100_000], "price": [58000.1, 57999.9],
                         "is_buyer_maker": [True, False]})


def test_write_interim_round_trip_keeps_types_and_provenance(tmp_path):
    path = interim_path("futures/um", "BTCUSDT", "aggTrades", "2024-08-05", root=tmp_path)
    meta = {"day": "2024-08-05", "code": "a0c0957", "params": {"window": 200}, "stats": {"rows_in": 2}}
    size = write_interim(_frame(), path, meta)
    assert path.relative_to(tmp_path).as_posix() == "futures/um/BTCUSDT/aggTrades/2024-08-05.parquet"
    assert size == path.stat().st_size and size > 0
    pd.testing.assert_frame_equal(pd.read_parquet(path), _frame())
    assert read_meta(path) == meta


def test_write_interim_replaces_whole_file_and_leaves_no_part(tmp_path):
    path = tmp_path / "day.parquet"
    write_interim(_frame(), path, {"run": 1})
    write_interim(_frame().iloc[:1], path, {"run": 2})
    assert len(pd.read_parquet(path)) == 1 and read_meta(path) == {"run": 2}
    assert list(tmp_path.rglob("*.part")) == []

            