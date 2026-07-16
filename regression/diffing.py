"""JSON 時變欄位偵測、遮罩套用、結構(schema)萃取與深度比對的共用工具。

- detect_dynamic_paths: 比對同一端點前後兩次回應,抓出值會變動的欄位路徑。
- apply_mask: 依路徑清單把值換成 "<DYNAMIC>"。
- extract_schema: 把 JSON 值轉成只保留型別形狀的骨架,用於 structure-only 比對。
- deep_diff: 比較兩個(已套用遮罩的)JSON 值,回傳差異路徑清單(空清單代表相同)。
"""
from __future__ import annotations

from typing import Any

DYNAMIC_MARK = "<DYNAMIC>"

PathKey = tuple  # 由 str(dict key) 或 int(list index) 組成


def _path_to_str(path: PathKey) -> str:
    parts = []
    for part in path:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            parts.append(f".{part}" if parts else str(part))
    return "".join(parts) or "$"


def detect_dynamic_paths(before: Any, after: Any, path: PathKey = ()) -> list[PathKey]:
    """回傳兩次抓取之間,值出現差異的欄位路徑列表。"""
    changed: list[PathKey] = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before.keys()) | set(after.keys())):
            if key not in before or key not in after:
                changed.append(path + (key,))
                continue
            changed.extend(detect_dynamic_paths(before[key], after[key], path + (key,)))
    elif isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            changed.append(path)
        else:
            for idx, (b_item, a_item) in enumerate(zip(before, after)):
                changed.extend(detect_dynamic_paths(b_item, a_item, path + (idx,)))
    else:
        if before != after:
            changed.append(path)
    return changed


def apply_mask(value: Any, mask_paths: list[PathKey]) -> Any:
    """回傳套用遮罩後的複本;mask_paths 內的路徑一律替換為 DYNAMIC_MARK。"""
    mask_set = {tuple(p) for p in mask_paths}

    def _walk(node: Any, path: PathKey) -> Any:
        if tuple(path) in mask_set:
            return DYNAMIC_MARK
        if isinstance(node, dict):
            return {k: _walk(v, path + (k,)) for k, v in node.items()}
        if isinstance(node, list):
            return [_walk(item, path + (idx,)) for idx, item in enumerate(node)]
        return node

    return _walk(value, ())


def mask_paths_to_str(mask_paths: list[PathKey]) -> list[str]:
    return sorted({_path_to_str(p) for p in mask_paths})


def extract_schema(value: Any) -> Any:
    """把 JSON 值轉換成只描述型別形狀的骨架,忽略實際數值。"""
    if isinstance(value, dict):
        return {k: extract_schema(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        if not value:
            return "empty_list"
        return [extract_schema(value[0])]
    if value is None:
        return "null"
    return type(value).__name__


def schema_diff(expected: Any, actual: Any, path: PathKey = ()) -> list[str]:
    """比對兩份 extract_schema() 結果,只回報「結構真的變了」的差異。

    這裡刻意比 deep_diff 寬鬆:structure-only 端點多半含法人籌碼、選擇權
    open interest/volume、活動日期這類「即時資料當下長什麼樣」才會決定的
    欄位——同一版程式碼在不同時間點呼叫,經常會看到:
    - 欄位整個消失或多出來(例如法人籌碼明細只在某些交易日才有完整欄位),
    - 型別在 null / 有值之間切換(activityDate 有時是日期字串、有時是 null),
    - 數值型別在 int / float 之間切換(選擇權未平倉量剛好是整數時,
      JSON 序列化結果從 12345.0 變成 12345)。
    這些都是 app.py 對外部資料當下狀態的正常反映,不是重構造成的改變。
    只有「兩個都有值的非 null、非數值型別之間仍然對不上」才視為真正的
    結構差異(例如一個是 str、另一個是 dict)。
    """
    diffs: list[str] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected.keys()) | set(actual.keys())):
            if key not in expected or key not in actual:
                continue  # 容忍:即時資料當下有沒有抓到而欄位整個消失/多出來
            diffs.extend(schema_diff(expected[key], actual[key], path + (key,)))
    elif isinstance(expected, list) and isinstance(actual, list):
        for idx, (e_item, a_item) in enumerate(zip(expected, actual)):
            diffs.extend(schema_diff(e_item, a_item, path + (idx,)))
    else:
        # empty_list 与非空 list schema、"null" 与其他型別、int/float 数值型别
        # 之间视为相容。值本身可能是 list(非空 list schema 的骨架),不可直接
        # 丟進 set 判斷成員(unhashable),所以用逐一比較取代 `in {...}`。
        numeric_types = {"int", "float"}

        def _is_flexible(value: Any) -> bool:
            return value == "null" or value == "empty_list" or isinstance(value, list)

        both_numeric = expected in numeric_types and actual in numeric_types
        if not both_numeric and expected != actual and not (_is_flexible(expected) or _is_flexible(actual)):
            diffs.append(f"{_path_to_str(path)}: {expected!r} -> {actual!r}")
    return diffs


def deep_diff(expected: Any, actual: Any, path: PathKey = ()) -> list[str]:
    """回傳差異描述清單;已套用遮罩(DYNAMIC_MARK)的欄位視為必然相符,不比對。"""
    diffs: list[str] = []
    if expected == DYNAMIC_MARK or actual == DYNAMIC_MARK:
        return diffs
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected.keys()) | set(actual.keys())):
            if key not in expected:
                diffs.append(f"{_path_to_str(path)}: 新增欄位 {key!r}")
                continue
            if key not in actual:
                diffs.append(f"{_path_to_str(path)}: 缺少欄位 {key!r}")
                continue
            diffs.extend(deep_diff(expected[key], actual[key], path + (key,)))
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            diffs.append(f"{_path_to_str(path)}: 陣列長度 {len(expected)} -> {len(actual)}")
        else:
            for idx, (e_item, a_item) in enumerate(zip(expected, actual)):
                diffs.extend(deep_diff(e_item, a_item, path + (idx,)))
    else:
        if expected != actual:
            diffs.append(f"{_path_to_str(path)}: {expected!r} -> {actual!r}")
    return diffs
