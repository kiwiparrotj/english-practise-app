# -*- coding: utf-8 -*-
"""
ECC 商务英语 / 日常英语 复习系统 v5
=================================
流程：① 设置画面选板块/学期/大类 + 选要玩的游戏 → ② 点"开始"才计时 → ③ 进入游戏
- 🃏 翻牌模式：点"我会了/还不熟"立即自动换下一题；"还不熟"自动计入待复习清单+重置熟练度
- ✍️ 智能遮罩填空：优先出待复习清单；挖空数量跟熟练度挂钩（越熟练挖得越多，1~4个）；
  默认纯空白，主动点"要提示"才给首字母
- 🧭 上下文场景本意选择：不变
- 🛠️ 数据管理：可搜索并单独修改/删除某一条题目
- 📖 历史记录：每次结束学习自动记一笔
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import os
import random
import hashlib
import time
import re
import io
import zipfile
from datetime import datetime

# ------------------------------------------------------------------
# 基础配置
# ------------------------------------------------------------------
st.set_page_config(page_title="ECC 英语复习系统", layout="wide", page_icon="📚")

DB_PATH = "my_comprehensive_flashcards.json"
BOARD_CONFIG_PATH = "board_config.json"
WEAK_PATH = "weak_review.json"
HISTORY_PATH = "study_history.json"
DEFAULT_BOARD_CONFIG = {"商务英语/面接": 56, "日常英语": 70}
EXPECTED_COLS = ["id", "category", "japanese", "chinese", "english_standard", "teacher_lecture"]

COL_KEYWORDS = {
    "id": ["id", "编号", "no", "number", "番号"],
    "category": ["category", "type", "大类", "topic", "class", "分类"],
    "japanese": ["japanese", "jp", "日语", "日本語"],
    "chinese": ["chinese", "cn", "中文"],
    "english_standard": ["english_standard", "english", "standard", "英语", "英文"],
    "teacher_lecture": ["teacher_lecture", "lecture", "teacher", "解说", "讲解", "名师"],
}

MODE_LABELS = {
    "flip": "🃏 翻牌模式",
    "mask": "✍️ 智能遮罩填空",
    "choice": "🧭 上下文场景本意选择",
}

# ------------------------------------------------------------------
# 全局样式
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;600;800&family=Noto+Sans+JP:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans SC', 'Noto Sans JP', sans-serif; }
    .stApp { background: linear-gradient(160deg, #f7f8ff 0%, #ffffff 45%, #fbfaff 100%); }

    .stTabs [data-baseweb="tab-list"] {
        gap: 16px; background: #f0f1fb; padding: 14px 14px 0 14px;
        border-radius: 20px 20px 0 0; margin-bottom: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 68px; white-space: pre-wrap; border-radius: 16px 16px 0 0;
        font-size: 1.3rem; font-weight: 800; padding: 10px 30px;
        background-color: #ffffff; box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border: 2px solid transparent;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6D5DF6, #4C6FFF) !important; color: white !important;
        box-shadow: 0 6px 18px rgba(108,93,246,0.4); border: 2px solid #4C6FFF;
    }
    .stTabs [data-baseweb="tab-panel"] {
        background: #ffffff; border-radius: 0 0 20px 20px; padding: 24px 4px 4px 4px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.04);
    }

    .kpi-row { display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap; justify-content:center; }
    .kpi-pill {
        display:inline-flex; align-items:center; gap:6px;
        background:white; border-radius:999px;
        padding:10px 22px; box-shadow:0 4px 14px rgba(108,99,255,0.10);
        border:1px solid #f0f0f8; font-weight:700; font-size:0.95rem;
    }
    .kpi-pill .num { font-size:1.1rem; font-weight:800; }
    .kpi-correct { color:#2fb872; }
    .kpi-wrong { color:#e6584f; }
    .kpi-accuracy { color:#8A80E8; }
    .kpi-weak { color:#e08a2c; }

    .study-box {
        background: linear-gradient(135deg, #ffffff, #f4f5ff); border-radius: 20px;
        padding: 28px 32px; box-shadow: 0 8px 24px rgba(108, 99, 255, 0.12);
        border: 1px solid #eceafd; margin-bottom: 18px;
    }
    .answer-box {
        background: linear-gradient(135deg, #eafff1, #f5fffa); border-radius: 16px;
        padding: 20px 26px; border: 1px solid #d3f5df; margin-top: 10px;
    }
    .lecture-box {
        background: linear-gradient(135deg, #fff8ea, #fffdf5); border-radius: 16px;
        padding: 20px 26px; border: 1px solid #fbe8b8; margin-top: 10px;
    }
    .meta-badge {
        display: inline-block; background: #eef0fb; color: #8A80E8; border-radius: 20px;
        padding: 4px 16px; font-size: 0.85rem; font-weight: 600; margin-bottom: 12px; margin-right:8px;
    }
    .weak-badge {
        display:inline-block; background:#ffe9d6; color:#e08a2c; border-radius:20px;
        padding:4px 16px; font-size:0.8rem; font-weight:700; margin-bottom:10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# 数据加载 / 保存
# ------------------------------------------------------------------
def load_data():
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_data(cards):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)


def load_board_config():
    cfg = dict(DEFAULT_BOARD_CONFIG)
    if os.path.exists(BOARD_CONFIG_PATH):
        try:
            with open(BOARD_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_board_config(cfg):
    with open(BOARD_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_weak():
    if os.path.exists(WEAK_PATH):
        try:
            with open(WEAK_PATH, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_weak(weak_set):
    with open(WEAK_PATH, "w", encoding="utf-8") as f:
        json.dump(list(weak_set), f, ensure_ascii=False, indent=2)


def load_history():
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def make_uid(card):
    board = card.get("board", "商务英语/面接")
    raw = f"{board}||{card['id']}||{card['japanese']}||{card['english_standard']}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


# ------------------------------------------------------------------
# CSV 列名鲁棒解析
# ------------------------------------------------------------------
def normalize_df_columns(df: pd.DataFrame):
    cleaned = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    df = df.copy()
    df.columns = cleaned

    mapping = {}
    for target, kws in COL_KEYWORDS.items():
        for col in cleaned:
            if any(kw in col for kw in kws):
                mapping[target] = col
                break

    missing = [t for t in EXPECTED_COLS if t not in mapping]
    if missing:
        if len(cleaned) == 6:
            mapping = dict(zip(EXPECTED_COLS, cleaned))
            st.warning(
                f"⚠️ 部分列名无法自动识别，已采用【物理顺序兜底映射】：{mapping}\n"
                f"请确认原始列顺序为：id, category, japanese, chinese, english_standard, teacher_lecture。"
            )
        else:
            st.error(
                f"❌ CSV 解析失败：检测到 {len(cleaned)} 列，非预期的 6 列，且缺少关键列 {missing}。"
                f"为避免生成错误数据，已终止导入，请检查文件后重新上传。"
            )
            return None

    df = df.rename(columns={v: k for k, v in mapping.items()})
    return df[EXPECTED_COLS]


def normalize_text(s: str) -> str:
    """去除多余空格并统一大小写，用于判断重复（不影响实际存储/显示的原文）"""
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def dedup_key(board, cid, japanese, english, ignore_board=False):
    b = "" if ignore_board else board
    return (b, str(cid), normalize_text(japanese), normalize_text(english))


def merge_new_cards(existing, new_df, board):
    existing_keys = set(
        dedup_key(c.get("board", "商务英语/面接"), c["id"], c["japanese"], c["english_standard"])
        for c in existing
    )
    added, skipped, bad_rows = 0, 0, 0

    for _, row in new_df.iterrows():
        try:
            cid = int(float(row["id"]))
        except Exception:
            bad_rows += 1
            continue

        japanese = str(row.get("japanese", "")).strip()
        english = str(row.get("english_standard", "")).strip()
        if not japanese or not english:
            bad_rows += 1
            continue

        key = dedup_key(board, cid, japanese, english)
        if key in existing_keys:
            skipped += 1
            continue

        card = {
            "id": cid,
            "board": board,
            "category": str(row.get("category", "")).strip() or "未分类",
            "japanese": japanese,
            "chinese": str(row.get("chinese", "")).strip(),
            "english_standard": english,
            "teacher_lecture": str(row.get("teacher_lecture", "")).strip(),
            "mastery": 0,
        }
        card["uid"] = make_uid(card)
        existing.append(card)
        existing_keys.add(key)
        added += 1

    return existing, added, skipped, bad_rows


def get_semester(cid: int, board: str, board_config: dict) -> str:
    size = board_config.get(board, 56)
    if size <= 0 or cid <= 0:
        return "其他"
    sem_idx = (cid - 1) // size + 1
    labels = ["第一学期", "第二学期", "第三学期", "第四学期"]
    if 1 <= sem_idx <= 4:
        return labels[sem_idx - 1]
    return "其他"


def masked_count_for(card, words):
    """挖空数量跟熟练度挂钩：越生疏挖得越少（至少1个），越熟练挖得越多（最多4个，且不挖整句）"""
    mastery = card.get("mastery", 0)
    upper_bound = max(len(words) - 1, 1)
    n = min(1 + mastery, 4, upper_bound)
    return max(n, 1)


def get_maskable_indices(words):
    """排除看起来像人名/专有名词的词（句中非首位、首字母大写的词），避免挖空考人名这种死记硬背的东西"""
    candidates = []
    for i, w in enumerate(words):
        core = w.strip(".,!?;:\"'()")
        looks_like_proper_noun = (
            i > 0 and core[:1].isupper() and core.isalpha() and core.lower() != "i"
        )
        if not looks_like_proper_noun:
            candidates.append(i)
    if not candidates:
        candidates = list(range(len(words)))  # 万一整句都被判定成专有名词，退回全部可选，避免无空可挖
    return candidates


def cleanup_duplicate_cards(ignore_board=False):
    """清理题库里已经存在的重复题目，保留第一条。
    ignore_board=True 时忽略板块字段差异（用于处理同一批内容被存进了不同拼写板块名的情况）"""
    seen = {}
    unique = []
    removed = 0
    for c in st.session_state.flashcards:
        k = dedup_key(c.get("board", "商务英语/面接"), c["id"], c["japanese"], c["english_standard"], ignore_board=ignore_board)
        if k not in seen:
            seen[k] = c
            unique.append(c)
        else:
            removed += 1
            if c["uid"] in st.session_state.weak_uids:
                st.session_state.weak_uids.discard(c["uid"])
                st.session_state.weak_uids.add(seen[k]["uid"])
    st.session_state.flashcards = unique
    save_data(unique)
    save_weak(st.session_state.weak_uids)
    return removed


def count_duplicates(ignore_board=False):
    seen = set()
    dup = 0
    for c in st.session_state.flashcards:
        k = dedup_key(c.get("board", "商务英语/面接"), c["id"], c["japanese"], c["english_standard"], ignore_board=ignore_board)
        if k in seen:
            dup += 1
        else:
            seen.add(k)
    return dup


def get_board_counts():
    counts = {}
    for c in st.session_state.flashcards:
        b = c.get("board", "商务英语/面接")
        counts[b] = counts.get(b, 0) + 1
    return counts


def build_backup_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in [DB_PATH, WEAK_PATH, HISTORY_PATH, BOARD_CONFIG_PATH]:
            if os.path.exists(path):
                zf.write(path, arcname=os.path.basename(path))
    buf.seek(0)
    return buf


# ------------------------------------------------------------------
# 初始化 session_state
# ------------------------------------------------------------------
if "flashcards" not in st.session_state:
    data = load_data()
    changed = False
    for c in data:
        if "mastery" not in c:
            c["mastery"] = 0
            changed = True
    st.session_state.flashcards = data
    if changed:
        save_data(data)

if "board_config" not in st.session_state:
    st.session_state.board_config = load_board_config()

if "weak_uids" not in st.session_state:
    st.session_state.weak_uids = load_weak()

if "study_history" not in st.session_state:
    st.session_state.study_history = load_history()

if "session_active" not in st.session_state:
    st.session_state.session_active = False

if "session_start_time" not in st.session_state:
    st.session_state.session_start_time = None

if "score" not in st.session_state:
    st.session_state.score = {"correct": 0, "wrong": 0}

for mkey in ["card_flip", "card_mask", "card_choice"]:
    if mkey not in st.session_state:
        st.session_state[mkey] = None


def register_score(uid, is_correct):
    scored_key = f"scored_{uid}"
    if st.session_state.get(scored_key):
        return
    st.session_state[scored_key] = True
    if is_correct:
        st.session_state.score["correct"] += 1
    else:
        st.session_state.score["wrong"] += 1


def add_to_weak(uid):
    st.session_state.weak_uids.add(uid)
    save_weak(st.session_state.weak_uids)


def remove_from_weak(uid):
    if uid in st.session_state.weak_uids:
        st.session_state.weak_uids.discard(uid)
        save_weak(st.session_state.weak_uids)


def set_mastery(card, delta):
    card["mastery"] = max(0, min(card.get("mastery", 0) + delta, 4))
    save_data(st.session_state.flashcards)


def pick_card(state_key, pool, prefer_weak=False, exclude_uid=None):
    candidates = pool
    if prefer_weak:
        weak_in_pool = [c for c in pool if c["uid"] in st.session_state.weak_uids]
        if weak_in_pool:
            candidates = weak_in_pool

    # 避免最近才出现过的题目马上又被抽到，减少"总是重复同一批"的感觉
    history_key = f"{state_key}_history"
    recent = st.session_state.get(history_key, [])
    exclude_set = set(recent)
    if exclude_uid:
        exclude_set.add(exclude_uid)

    narrowed = [c for c in candidates if c["uid"] not in exclude_set]
    if narrowed:
        candidates = narrowed
    elif exclude_uid:
        narrowed2 = [c for c in candidates if c["uid"] != exclude_uid]
        if narrowed2:
            candidates = narrowed2
    if not candidates:
        candidates = pool

    chosen = random.choice(candidates)
    st.session_state[state_key] = chosen
    st.session_state[f"{state_key}_start"] = time.time()
    recent.append(chosen["uid"])
    st.session_state[history_key] = recent[-5:]


def clear_mode_state(uid_prefix_list):
    for k in list(st.session_state.keys()):
        if any(k.startswith(p) for p in uid_prefix_list):
            del st.session_state[k]


# ------------------------------------------------------------------
# 侧边栏：题库管理（任何时候都可以上传）
# ------------------------------------------------------------------
st.sidebar.header("📂 题库管理")

board_config = st.session_state.board_config
preset_boards = list(board_config.keys())
board_display_options = [f"{b}（每学期{board_config[b]}题）" for b in preset_boards] + ["➕ 自定义新板块"]
board_sel = st.sidebar.selectbox("这份 CSV 属于哪个板块", board_display_options)

custom_size = 56
if board_sel == "➕ 自定义新板块":
    custom_name = st.sidebar.text_input("新板块名称", placeholder="例如：日常英语")
    custom_size = st.sidebar.number_input("该板块每学期题数", min_value=1, value=56, step=1)
    target_board = custom_name.strip()
else:
    target_board = preset_boards[board_display_options.index(board_sel)]

uploaded_file = st.sidebar.file_uploader("拖拽上传 CSV 题库文件", type=["csv"])
if uploaded_file is not None:
    if not target_board:
        st.sidebar.error("请先填写新板块名称，再上传文件。")
    else:
        try:
            raw_df = pd.read_csv(uploaded_file)
        except Exception:
            uploaded_file.seek(0)
            raw_df = pd.read_csv(uploaded_file, encoding="utf-8-sig")

        norm_df = normalize_df_columns(raw_df)
        if norm_df is not None:
            if target_board not in board_config:
                board_config[target_board] = int(custom_size)
                save_board_config(board_config)
                st.session_state.board_config = board_config

            merged, added, skipped, bad_rows = merge_new_cards(
                st.session_state.flashcards, norm_df, target_board
            )
            st.session_state.flashcards = merged
            save_data(merged)
            msg = f"✅ 已导入至【{target_board}】：新增 {added} 条，去重跳过 {skipped} 条"
            if bad_rows:
                msg += f"，⚠️ {bad_rows} 行因编号/内容缺失被忽略（未生成任何随机编号）"
            st.sidebar.success(msg)

st.sidebar.caption(f"当前题库总量：{len(st.session_state.flashcards)} 条")

with st.sidebar.expander("🔍 查看板块分布 / 诊断重复"):
    for b, cnt in get_board_counts().items():
        st.write(f"「{b}」：{cnt} 条")
    dup_same_board = count_duplicates(ignore_board=False)
    dup_ignore_board = count_duplicates(ignore_board=True)
    st.caption(f"同板块内重复：{dup_same_board} 条")
    st.caption(f"忽略板块差异后重复：{dup_ignore_board} 条")
    if dup_ignore_board > dup_same_board:
        st.warning(
            f"有 {dup_ignore_board - dup_same_board} 条内容其实是同一句话，"
            f"但存在了拼写不同的板块名下——用下面「深度清理」可以合并。"
        )

col_clean, col_backup = st.sidebar.columns(2)
with col_clean:
    if st.button("🧹 清理重复", use_container_width=True):
        removed = cleanup_duplicate_cards(ignore_board=False)
        if removed:
            st.sidebar.success(f"已清理 {removed} 条重复题目")
        else:
            st.sidebar.info("同板块内没有发现重复")
        st.rerun()
with col_backup:
    st.download_button(
        "📤 导出备份",
        data=build_backup_zip(),
        file_name=f"ecc_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
        mime="application/zip",
        use_container_width=True,
    )

if st.sidebar.button("🧹🧹 深度清理（忽略板块拼写差异）", use_container_width=True):
    removed = cleanup_duplicate_cards(ignore_board=True)
    if removed:
        st.sidebar.success(f"已合并清理 {removed} 条重复题目（保留最早那条所属的板块）")
    else:
        st.sidebar.info("没有发现跨板块的重复")
    st.rerun()

st.sidebar.header("📌 待复习清单")
weak_count = len(st.session_state.weak_uids)
st.sidebar.caption(f"目前有 {weak_count} 条不熟悉的句子（智能遮罩填空会自动优先出这些题）")

if st.session_state.session_active:
    st.sidebar.header("⏳ 学习中")
    elapsed_min = int((time.time() - st.session_state.session_start_time) // 60)
    st.sidebar.caption(f"已进行 {elapsed_min} 分钟")
    if st.sidebar.button("🏁 结束本次学习并记录", type="primary", use_container_width=True):
        _score = st.session_state.score
        _total = _score["correct"] + _score["wrong"]
        _acc = round(_score["correct"] / _total * 100) if _total else 0
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "boards": st.session_state.get("active_boards", []),
            "semesters": st.session_state.get("active_semesters", []),
            "mode": MODE_LABELS.get(st.session_state.get("active_mode", ""), ""),
            "correct": _score["correct"],
            "wrong": _score["wrong"],
            "accuracy": _acc,
            "weak_count": len(st.session_state.weak_uids),
            "duration_min": int((time.time() - st.session_state.session_start_time) // 60),
        }
        st.session_state.study_history.insert(0, entry)
        save_history(st.session_state.study_history)
        st.session_state.session_active = False
        st.session_state.session_start_time = None
        # 清空上次的范围选择，避免下次设置画面里残留旧的板块/学期选中状态
        st.session_state.setup_boards = set()
        st.session_state.setup_semesters = set()
        for mkey in ["card_flip", "card_mask", "card_choice"]:
            st.session_state[mkey] = None
        st.sidebar.success("✅ 已记录本次学习！")
        st.rerun()

with st.sidebar.expander("📖 历史学习记录"):
    if not st.session_state.study_history:
        st.caption("暂无记录，结束一次学习后会显示在这里。")
    else:
        for h in st.session_state.study_history[:15]:
            boards_txt = "、".join(h.get("boards", [])) or "—"
            st.markdown(
                f"**{h['timestamp']}**　{h.get('mode','')}　{boards_txt}\n\n"
                f"✅{h['correct']} ❌{h['wrong']} ｜ 🎯{h['accuracy']}% ｜ "
                f"📌待复习{h['weak_count']} ｜ ⏳{h.get('duration_min',0)}分钟"
            )
            st.markdown("---")

# ------------------------------------------------------------------
# 主界面
# ------------------------------------------------------------------
st.title("📚 ECC 就职面试 / 商务英语 复习系统")

if not st.session_state.flashcards:
    st.info("目前题库为空，请先在左侧上传 CSV 题库文件。")
    st.stop()

all_boards = sorted(set(board_config.keys()) | set(c.get("board", "") for c in st.session_state.flashcards))
all_semesters = ["第一学期", "第二学期", "第三学期", "第四学期", "其他"]
all_categories = sorted(set(c.get("category", "未分类") for c in st.session_state.flashcards))

# ==================================================================
# ① 设置画面：选范围 + 选游戏 → 点开始才计时（全部用大按钮，状态一目了然）
# 说明：只保留"板块"这一层分类（比如 商务英语 / 日常英语），
# 不再单独显示"大类"筛选，避免跟板块混淆。
# ==================================================================
if not st.session_state.session_active:
    if "setup_boards" not in st.session_state:
        st.session_state.setup_boards = set()  # 默认不预选，点哪个才是哪个
    if "setup_semesters" not in st.session_state:
        st.session_state.setup_semesters = set()
    if "setup_mode" not in st.session_state:
        st.session_state.setup_mode = "flip"

    st.markdown("### ① 选择要学习的板块")
    st.caption("点击按钮＝选中该板块（可以同时选两个）")
    b_cols = st.columns(len(all_boards)) if all_boards else []
    for col, b in zip(b_cols, all_boards):
        selected = b in st.session_state.setup_boards
        with col:
            if st.button(("✅ " if selected else "") + b, key=f"boardbtn_{b}",
                         type="primary" if selected else "secondary", use_container_width=True):
                if selected:
                    st.session_state.setup_boards.discard(b)
                else:
                    st.session_state.setup_boards.add(b)
                st.rerun()

    st.markdown("### ② 选择学期")
    st.caption("点击按钮＝选中该学期（可以同时选多个）")
    s_cols = st.columns(len(all_semesters))
    for col, s in zip(s_cols, all_semesters):
        selected = s in st.session_state.setup_semesters
        with col:
            if st.button(("✅ " if selected else "") + s, key=f"sembtn_{s}",
                         type="primary" if selected else "secondary", use_container_width=True):
                if selected:
                    st.session_state.setup_semesters.discard(s)
                else:
                    st.session_state.setup_semesters.add(s)
                st.rerun()

    st.markdown("### ③ 选择要玩的游戏")
    m_cols = st.columns(3)
    for col, (mkey, mlabel) in zip(m_cols, MODE_LABELS.items()):
        selected = st.session_state.setup_mode == mkey
        with col:
            if st.button(mlabel, key=f"modepick_{mkey}",
                         type="primary" if selected else "secondary", use_container_width=True):
                st.session_state.setup_mode = mkey
                st.rerun()

    st.write("")
    ready = bool(st.session_state.setup_boards) and bool(st.session_state.setup_semesters)
    if not ready:
        st.warning("请至少选择一个板块和一个学期。")
    if st.button("🚀 开始学习（点击后才开始计时）", type="primary", use_container_width=True, disabled=not ready):
        st.session_state.active_boards = list(st.session_state.setup_boards)
        st.session_state.active_semesters = list(st.session_state.setup_semesters)
        st.session_state.active_categories = all_categories  # 不再单独筛选大类，全部包含
        st.session_state.active_mode = st.session_state.setup_mode
        st.session_state.session_active = True
        st.session_state.session_start_time = time.time()
        st.session_state.score = {"correct": 0, "wrong": 0}
        clear_mode_state(("scored_",))
        st.rerun()

    st.stop()

# ------------------------------------------------------------------
# ② 已开始：计算题库范围
# ------------------------------------------------------------------
selected_boards = st.session_state.active_boards
selected_semesters = st.session_state.active_semesters
selected_categories = st.session_state.active_categories

filtered_pool = [
    c
    for c in st.session_state.flashcards
    if c.get("board", "商务英语/面接") in selected_boards
    and get_semester(c["id"], c.get("board", "商务英语/面接"), board_config) in selected_semesters
    and c.get("category", "未分类") in selected_categories
]

if not filtered_pool:
    st.warning("当前范围内没有题目，请结束本次学习后重新设置范围。")
    st.stop()

_pool_board_counts = {}
for _c in filtered_pool:
    _b = _c.get("board", "商务英语/面接")
    _pool_board_counts[_b] = _pool_board_counts.get(_b, 0) + 1
_pool_board_summary = "、".join(f"{b}×{n}" for b, n in _pool_board_counts.items())
st.caption(
    f"🔧 本次范围：板块 [{'、'.join(selected_boards)}] ｜ 学期 [{'、'.join(selected_semesters)}] "
    f"→ 实际抽题池 {len(filtered_pool)} 条（{_pool_board_summary}）"
)
if len(_pool_board_counts) > 1:
    st.warning(
        "⚠️ 抽题池里出现了不止一个板块，说明有些题目的「板块」标签跟你想的不一样"
        "（很可能是之前深度清理时被合并到了错的板块下）。可以到侧边栏「🔍 查看板块分布」核对，"
        "或用题目上的「✏️ 这题有错？直接改这一条」把它的板块改回来。"
    )

pool_uids = {c["uid"] for c in filtered_pool}

if st.session_state.card_flip is None or st.session_state.card_flip["uid"] not in pool_uids:
    pick_card("card_flip", filtered_pool)
if st.session_state.card_mask is None or st.session_state.card_mask["uid"] not in pool_uids:
    pick_card("card_mask", filtered_pool, prefer_weak=True)
if st.session_state.card_choice is None or st.session_state.card_choice["uid"] not in pool_uids:
    pick_card("card_choice", filtered_pool)

# KPI 胶囊
score = st.session_state.score
total = score["correct"] + score["wrong"]
accuracy = f"{(score['correct'] / total * 100):.0f}%" if total else "—"
st.markdown(
    f"""
    <div class="kpi-row">
        <div class="kpi-pill kpi-correct">✅ <span class="num">{score['correct']}</span> 正确</div>
        <div class="kpi-pill kpi-wrong">❌ <span class="num">{score['wrong']}</span> 错误</div>
        <div class="kpi-pill kpi-accuracy">🎯 <span class="num">{accuracy}</span> 正确率</div>
        <div class="kpi-pill kpi-weak">📌 <span class="num">{weak_count}</span> 待复习</div>
    </div>
    """,
    unsafe_allow_html=True,
)

session_start_ms = int(st.session_state.session_start_time * 1000)
components.html(
    f"""
    <div style="font-family:'Noto Sans SC',sans-serif; padding:2px 4px 10px 4px; text-align:center;">
        <span style="font-size:0.78rem; color:#999;">⏳ 本次学习时长　</span>
        <span id="session-timer" style="font-size:1.05rem; font-weight:700; color:#8A80E8;">00:00</span>
    </div>
    <script>
    const startS = {session_start_ms};
    function tick() {{
        const diff = Math.floor((Date.now() - startS) / 1000);
        const m = String(Math.floor(diff / 60)).padStart(2, '0');
        const s = String(diff % 60).padStart(2, '0');
        document.getElementById('session-timer').innerText = m + ':' + s;
    }}
    tick(); setInterval(tick, 1000);
    </script>
    """,
    height=36,
)

# 把用户在设置画面选的游戏排在第一个标签
ordered_keys = [st.session_state.active_mode] + [k for k in MODE_LABELS if k != st.session_state.active_mode]
tabs = st.tabs([MODE_LABELS[k] for k in ordered_keys])
tab_map = dict(zip(ordered_keys, tabs))


def render_meta(card):
    board = card.get("board", "商务英语/面接")
    mastery_dots = "●" * card.get("mastery", 0) + "○" * (4 - card.get("mastery", 0))
    st.markdown(
        f"<span class='meta-badge'>{board} ｜ 编号 #{card['id']} ｜ "
        f"{get_semester(card['id'], board, board_config)} ｜ {card.get('category','未分类')}</span>"
        f"<span class='meta-badge'>熟练度 {mastery_dots}</span>",
        unsafe_allow_html=True,
    )


def render_quick_edit(card, context_key):
    """直接修改/删除当前正在看的这一条题目，按 uid 精确定位，不用去底部搜索（避免同编号多条内容时搜错）"""
    uid = card["uid"]
    board_options = sorted(set(st.session_state.board_config.keys()) | {card.get("board", "商务英语/面接")})
    with st.expander("✏️ 这题有错？直接改这一条"):
        with st.form(key=f"quickedit_{context_key}_{uid}"):
            new_board = st.selectbox(
                "板块 board", board_options,
                index=board_options.index(card.get("board", "商务英语/面接")),
                key=f"qe_board_{context_key}_{uid}",
            )
            new_id = st.number_input("编号 id", value=int(card["id"]), step=1, key=f"qe_id_{context_key}_{uid}")
            new_category = st.text_input("大类 category", value=card.get("category", ""), key=f"qe_cat_{context_key}_{uid}")
            new_japanese = st.text_area("日语 japanese", value=card.get("japanese", ""), height=70, key=f"qe_jp_{context_key}_{uid}")
            new_chinese = st.text_area("中文 chinese", value=card.get("chinese", ""), height=70, key=f"qe_cn_{context_key}_{uid}")
            new_english = st.text_area("英语 english_standard", value=card.get("english_standard", ""), height=70, key=f"qe_en_{context_key}_{uid}")
            new_lecture = st.text_area("名师解说 teacher_lecture", value=card.get("teacher_lecture", ""), height=90, key=f"qe_lec_{context_key}_{uid}")
            col_s, col_d = st.columns(2)
            save_clicked = col_s.form_submit_button("💾 保存修改", use_container_width=True)
            delete_clicked = col_d.form_submit_button("🗑️ 删除此条", use_container_width=True)

        if save_clicked:
            card["board"] = new_board
            card["id"] = int(new_id)
            card["category"] = new_category.strip() or "未分类"
            card["japanese"] = new_japanese.strip()
            card["chinese"] = new_chinese.strip()
            card["english_standard"] = new_english.strip()
            card["teacher_lecture"] = new_lecture.strip()
            new_uid = make_uid(card)
            if new_uid != card["uid"]:
                remove_from_weak(card["uid"])
                card["uid"] = new_uid
            save_data(st.session_state.flashcards)
            st.success("✅ 已保存，点「换一题/下一题」后新内容就会用上。")

        if delete_clicked:
            remove_from_weak(card["uid"])
            st.session_state.flashcards = [c for c in st.session_state.flashcards if c["uid"] != card["uid"]]
            save_data(st.session_state.flashcards)
            st.success("🗑️ 已删除该条题目。")
            return True
    return False


def render_timer(state_key, label, color, frozen_seconds=None):
    if frozen_seconds is not None:
        m = int(frozen_seconds // 60)
        s = int(frozen_seconds % 60)
        st.caption(f"{label}⏹ {m:02d}:{s:02d}（已完成，用时定格）")
        return
    start_ms = int(st.session_state.get(f"{state_key}_start", time.time()) * 1000)
    components.html(
        f"""
        <div style="font-family:'Noto Sans SC',sans-serif;">
            <span style="font-size:0.85rem; color:#888;">{label}</span>
            <span id="timer-{state_key}" style="font-size:1rem; font-weight:700; color:{color};">00:00</span>
        </div>
        <script>
        const start = {start_ms};
        function tick() {{
            const diff = Math.floor((Date.now() - start) / 1000);
            const m = String(Math.floor(diff / 60)).padStart(2, '0');
            const s = String(diff % 60).padStart(2, '0');
            document.getElementById('timer-{state_key}').innerText = m + ':' + s;
        }}
        tick(); setInterval(tick, 1000);
        </script>
        """,
        height=30,
    )


# ==================================================================
# 模式 1：翻牌模式
# ==================================================================
with tab_map["flip"]:
    card = st.session_state.card_flip
    uid = card["uid"]
    render_meta(card)
    if render_quick_edit(card, "flip"):
        pick_card("card_flip", filtered_pool)
        st.rerun()

    japanese_html = card["japanese"].replace("'", "&#39;")
    chinese_html = card["chinese"].replace("'", "&#39;")
    english_html = card["english_standard"].replace("'", "&#39;")
    lecture_html = card["teacher_lecture"].replace("'", "&#39;")

    flip_component = f"""
    <div style="font-family:'Noto Sans SC','Noto Sans JP',sans-serif; perspective:1200px; max-width:820px; margin:0 auto;">
      <style>
        .flip-card {{ background-color: transparent; width: 100%; height: 260px; cursor: pointer; }}
        .flip-inner {{
          position: relative; width: 100%; height: 100%; text-align: center;
          transition: transform 0.6s cubic-bezier(.4,.2,.2,1); transform-style: preserve-3d;
        }}
        .flip-card.flipped .flip-inner {{ transform: rotateY(180deg); }}
        .flip-front, .flip-back {{
          position: absolute; width: 100%; height: 100%; backface-visibility: hidden;
          border-radius: 20px; display: flex; flex-direction: column; align-items: center;
          justify-content: center; padding: 20px; box-shadow: 0 10px 30px rgba(108,99,255,0.18);
        }}
        .flip-front {{ background: linear-gradient(135deg, #6D5DF6, #4C6FFF); color: white; }}
        .flip-back {{
          background: linear-gradient(135deg, #eafff1, #d9fbe6); color: #1b3b2c;
          transform: rotateY(180deg); overflow-y: auto;
        }}
        .flip-hint {{ position:absolute; bottom:10px; right:16px; font-size:0.75rem; opacity:0.85; }}
        .jp-text {{ font-size:1.7rem; font-weight:800; margin-bottom:10px; }}
        .cn-text {{ font-size:1.1rem; opacity:0.9; }}
        .en-text {{ font-size:1.35rem; font-weight:800; margin-bottom:12px; }}
        .lec-text {{ font-size:0.95rem; line-height:1.5; padding: 0 10px; }}
      </style>
      <div class="flip-card" onclick="this.classList.toggle('flipped')">
        <div class="flip-inner">
          <div class="flip-front">
            <div class="jp-text">{japanese_html}</div>
            <div class="cn-text">{chinese_html}</div>
            <div class="flip-hint">👆 点击卡片翻面</div>
          </div>
          <div class="flip-back">
            <div class="en-text">{english_html}</div>
            <div class="lec-text">{lecture_html}</div>
            <div class="flip-hint">👆 点击卡片翻回</div>
          </div>
        </div>
      </div>
    </div>
    """
    components.html(flip_component, height=300)

    st.write("")
    st.caption("看完背面后自评一下——两个按钮都会立刻自动跳下一题；「还不熟」会存进待复习清单并降低熟练度：")
    sc1, sc2 = st.columns(2)
    with sc1:
        if st.button("👍 我会了", key=f"know_{uid}", use_container_width=True):
            register_score(uid, True)
            remove_from_weak(uid)
            set_mastery(card, +1)
            pick_card("card_flip", filtered_pool, exclude_uid=uid)
            st.rerun()
    with sc2:
        if st.button("👎 还不熟", key=f"unknow_{uid}", use_container_width=True):
            register_score(uid, False)
            add_to_weak(uid)
            set_mastery(card, -4)  # 直接打回最生疏，下次填空少挖字
            pick_card("card_flip", filtered_pool, exclude_uid=uid)
            st.rerun()

    render_timer("card_flip", "⏱ 本题用时　", "#e08a2c")

# ==================================================================
# 模式 2：智能遮罩填空
# ==================================================================
with tab_map["mask"]:
    card = st.session_state.card_mask
    uid = card["uid"]
    render_meta(card)
    if render_quick_edit(card, "mask"):
        pick_card("card_mask", filtered_pool, prefer_weak=True)
        st.rerun()

    if uid in st.session_state.weak_uids:
        st.markdown("<span class='weak-badge'>📌 来自待复习清单</span>", unsafe_allow_html=True)

    words = card["english_standard"].split()

    mask_key = f"mask_{uid}"
    if mask_key not in st.session_state:
        maskable = get_maskable_indices(words)
        n = min(masked_count_for(card, words), len(maskable)) if words else 0
        st.session_state[mask_key] = sorted(random.sample(maskable, n)) if n else []
    masked_indices = st.session_state[mask_key]

    hint_shown_key = f"hintshown_{uid}"
    if hint_shown_key not in st.session_state:
        st.session_state[hint_shown_key] = False
    hint_shown = st.session_state[hint_shown_key]

    display_tokens = []
    for i, w in enumerate(words):
        if i not in masked_indices:
            display_tokens.append(w)
            continue
        if hint_shown:
            core = w.strip(".,!?;:")
            trailing = w[len(core):]
            first = core[0] if core else "_"
            blanks = "_" * max(len(core) - 1, 1)
            display_tokens.append(f"[ {first}{blanks}{trailing} ]")
        else:
            display_tokens.append("[ _______ ]")

    st.markdown(
        f"""<div class='study-box'>
        <b>请补全下列句子（本题挖空 {len(masked_indices)} 处，先靠自己回忆）：</b>
        <h3>{' '.join(display_tokens)}</h3>
        <p><i>日语提示：{card['japanese']}　｜　中文辅助：{card['chinese']}</i></p>
        </div>""",
        unsafe_allow_html=True,
    )

    if masked_indices and not hint_shown:
        if st.button("💡 想不起来？给个首字母提示", key=f"hintbtn_{uid}"):
            st.session_state[hint_shown_key] = True
            st.rerun()

    input_cols = st.columns(len(masked_indices)) if masked_indices else []
    user_inputs = []
    for pos, idx in enumerate(masked_indices):
        with input_cols[pos]:
            val = st.text_input(f"空格 {pos + 1}", key=f"blank_{uid}_{idx}")
            user_inputs.append(val)

    checked_key = f"checked_{uid}"
    elapsed_key = f"elapsed_mask_{uid}"
    if st.button("✅ 验证答案", key=f"verify_{uid}"):
        st.session_state[checked_key] = True
        if elapsed_key not in st.session_state:
            st.session_state[elapsed_key] = time.time() - st.session_state.get("card_mask_start", time.time())

    if st.session_state.get(checked_key):
        results = []
        for pos, idx in enumerate(masked_indices):
            correct_word = words[idx].strip(".,!?;:").lower()
            user_word = (user_inputs[pos] or "").strip(".,!?;:").lower()
            is_correct = user_word == correct_word
            results.append(is_correct)
            icon = "✅" if is_correct else "❌"
            st.write(f"{icon} 空格 {pos + 1}：你的答案「{user_inputs[pos]}」 —— 正确答案「{words[idx]}」")

        all_correct = bool(results) and all(results)
        register_score(uid, all_correct)
        if all_correct:
            st.balloons()
            set_mastery(card, +1)
            if uid in st.session_state.weak_uids:
                remove_from_weak(uid)
                st.info("🎉 已从『待复习清单』移除，掌握了！下次这句会挖更多空。")
        else:
            set_mastery(card, -1)

        st.write("")
        if st.button("➡️ 下一题", key=f"next_mask_top_{uid}", type="primary", use_container_width=True):
            pick_card("card_mask", filtered_pool, prefer_weak=True, exclude_uid=uid)
            st.rerun()

        st.markdown(f"<div class='answer-box'><b>完整原文：</b>{card['english_standard']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='lecture-box'><b>名师解说：</b>{card['teacher_lecture']}</div>", unsafe_allow_html=True)
        render_timer("card_mask", "⏱ 本题用时　", "#e08a2c", frozen_seconds=st.session_state.get(elapsed_key))
    else:
        st.write("")
        if st.button("➡️ 跳过，换一题", key=f"next_mask_{uid}"):
            pick_card("card_mask", filtered_pool, prefer_weak=True, exclude_uid=uid)
            st.rerun()
        render_timer("card_mask", "⏱ 本题用时　", "#e08a2c")

# ==================================================================
# 模式 3：上下文场景本意选择
# ==================================================================
with tab_map["choice"]:
    card = st.session_state.card_choice
    uid = card["uid"]
    render_meta(card)
    if render_quick_edit(card, "choice"):
        pick_card("card_choice", filtered_pool)
        st.rerun()

    st.markdown(
        f"<div class='study-box'><h2 style='text-align:center; margin:0;'>{card['english_standard']}</h2></div>",
        unsafe_allow_html=True,
    )
    st.caption("请选出与上句最贴切的中文/日语场景本意（四选一）：")

    pool_key = f"options_{uid}"
    if pool_key not in st.session_state:
        card_board = card.get("board", "商务英语/面接")
        distractor_candidates = [c for c in filtered_pool if c["uid"] != uid and c.get("board", "商务英语/面接") == card_board]
        if len(distractor_candidates) < 3:
            distractor_candidates = [c for c in filtered_pool if c["uid"] != uid]
        n_distractors = min(3, len(distractor_candidates))
        distractors = random.sample(distractor_candidates, n_distractors) if n_distractors else []
        options = [card["japanese"]] + [d["japanese"] for d in distractors]
        random.shuffle(options)
        st.session_state[pool_key] = options

    options = st.session_state[pool_key]
    choice_key = f"choice_{uid}"
    selected = st.radio("选项：", options, key=choice_key, index=None)

    answered_key = f"answered_{uid}"
    elapsed_key = f"elapsed_choice_{uid}"
    if st.button("✅ 提交答案", key=f"submit_{uid}", use_container_width=True):
        st.session_state[answered_key] = True
        if elapsed_key not in st.session_state:
            st.session_state[elapsed_key] = time.time() - st.session_state.get("card_choice_start", time.time())

    if st.session_state.get(answered_key):
        is_correct = selected == card["japanese"]
        register_score(uid, is_correct)
        if is_correct:
            st.success("🎉 回答正确！")
            remove_from_weak(uid)
        else:
            st.error(f"❌ 回答错误。正确答案是：{card['japanese']}")
        st.markdown(f"<div class='lecture-box'><b>名师语感与脉络拆解：</b>{card['teacher_lecture']}</div>", unsafe_allow_html=True)

    st.write("")
    if st.button("➡️ 下一题", key=f"next_choice_{uid}", type="primary", use_container_width=True):
        pick_card("card_choice", filtered_pool, exclude_uid=uid)
        st.rerun()

    render_timer("card_choice", "⏱ 本题用时　", "#e08a2c", frozen_seconds=st.session_state.get(elapsed_key) if st.session_state.get(answered_key) else None)

