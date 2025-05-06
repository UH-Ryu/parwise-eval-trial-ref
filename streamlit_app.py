import os
import json
import streamlit as st
import random
import datetime
import gspread
from google.oauth2 import service_account
import pandas as pd

# パスを追加
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utils.fixed_container import st_fixed_container

# 定数定義
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "data", "outputs")
PERSONA_FILE = os.path.join(BASE_DIR, "data", "persona_sample.jsonl")
SEEN_TEST_FILE = os.path.join(BASE_DIR, "data", "seen_test.jsonl")
SPREADSHEET_URL = st.secrets["SPREADSHEET_URL"]  # スプレッドシートのURLを環境変数から取得
SHEET_NAME = "シート1"  # シート名
SEED = 42 
# シード値を固定することで毎回同じサンプルが選ばれるようにする
random.seed(SEED)

# サンプル数の設定（バックエンド側で固定）
SAMPLE_SIZE = 5  # 評価に使用するサンプル数

# タイムスタンプの日本時間対応
t_delta = datetime.timedelta(hours=9)  # 9時間
JST = datetime.timezone(t_delta, 'JST')  # UTCから9時間差の「JST」タイムゾーン

# 利用可能なモデルのリスト
AVAILABLE_MODELS = [
    "gpt4o_conv_sample",
    "gpt4o_mini_conv_sample", 
    "nekomata_conv_sample",
    "sarashina_conv_sample",
    "swallow_conv_sample"
]

# ------------------------------
# Google Sheets関連の関数
# ------------------------------
def connect_to_google_sheets():
    """Google Sheetsに接続する"""
    try:
        # 新しい認証方法
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=scope
        )
        gc = gspread.authorize(credentials)
        
        worksheet = gc.open_by_url(SPREADSHEET_URL).worksheet(SHEET_NAME)

        return worksheet
    except Exception as e:
        st.error(f"Google Sheetsへの接続エラー: {str(e)}")
        return None

def save_to_google_sheets(evaluation_data):
    """評価データをGoogle Sheetsに保存する"""
    try:
        worksheet = connect_to_google_sheets()
        if not worksheet:
            return False
            
        # データを保存する行を準備
        rows_to_add = []
        user_id = evaluation_data["user_id"]
        timestamp = evaluation_data["timestamp"]
        
        for key, eval_item in evaluation_data["evaluations"].items():
            row = [
                user_id,
                timestamp,
                eval_item["page"],
                eval_item["original_index"],
                eval_item["model_a"],
                eval_item["model_b"],
                eval_item["winner"]
            ]
            rows_to_add.append(row)
        
        # 一括で行を追加
        if rows_to_add:
            worksheet.append_rows(rows_to_add)
            
        return True
    except Exception as e:
        st.error(f"Google Sheetsへの保存エラー: {str(e)}")
        return False

# ------------------------------
# ユーティリティ関数
# ------------------------------
def load_json(filepath):
    """JSONファイルを読み込むヘルパー関数"""
    data = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():  # 空行をスキップ
                    data.append(json.loads(line))
        return data
    except FileNotFoundError:
        st.error(f"ファイルが見つかりません: {filepath}")
        return []
    except json.JSONDecodeError:
        st.error(f"JSONフォーマットが不正です: {filepath}")
        return []

def load_jsonl(filepath):
    """JSONLファイルを読み込むヘルパー関数"""
    data = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():  # 空行をスキップ
                    data.append(json.loads(line))
        return data
    except FileNotFoundError:
        st.error(f"ファイルが見つかりません: {filepath}")
        return []
    except json.JSONDecodeError as e:
        st.error(f"JSONフォーマットが不正です: {filepath} - {str(e)}")
        return []

def save_json(data, filepath):
    """JSONファイルに保存するヘルパー関数"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"保存中にエラーが発生しました: {e}")
        return False

def load_model_responses():
    """すべてのモデルの応答を読み込む"""
    model_responses = {}
    
    for model_name in AVAILABLE_MODELS:
        filepath = os.path.join(OUTPUTS_DIR, f"{model_name}.jsonl")
        model_responses[model_name] = load_jsonl(filepath)
    
    return model_responses

def load_persona_data():
    """ペルソナデータを読み込む"""
    return load_json(PERSONA_FILE)

def load_seen_test_data():
    """テストデータを読み込む"""
    return load_jsonl(SEEN_TEST_FILE)


def sample_test_data(test_data, sample_size):
    """テストデータからランダムにサンプリングする"""
    if sample_size >= len(test_data):
        return test_data
    
    
    return random.sample(test_data, sample_size)

# ------------------------------
# UI関連の関数
# ------------------------------
def create_rounded_box(content, bg_color="lightgray", text_color="black", 
                       height=None, enable_scroll=False):
    """統合された角丸ボックス作成関数"""
    style = f"""
        background-color: {bg_color};
        color: {text_color};
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 10px;
    """
    
    if height:
        style += f"height: {height};"
    
    if enable_scroll:
        style += "overflow: scroll; white-space: pre-wrap;"
    
    return f'<div style="{style}">{content}</div>'

def display_conversation(context_data):
    """会話履歴を表示する関数"""
    st.markdown("### 対話履歴")
    
    # JSONLからのデータを適切な形式に変換
    messages = []
    context = context_data.get("context", "")
    speaker = context_data.get("speaker", "")
    
    # 会話形式に変換
    for part in context:
        current_speaker = list(part.keys())[0]
        current_utterance = part[current_speaker]
        messages.append({"role": current_speaker, "message": current_utterance})

    # 会話メッセージを表示
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("message", "")

        if role == speaker:
            with st.chat_message("assistant"):
                st.markdown(role)
                st.markdown(content)
        else:
            with st.chat_message("user"):
                st.markdown(role)
                st.markdown(content)


def display_model_response(response, model_name, box_color):
    """モデルの応答を表示する関数"""
    st.markdown(f"**{model_name}**")
    st.markdown(create_rounded_box(response, bg_color=box_color), unsafe_allow_html=True)

def display_response_options(page, model_pair, model_responses, conversation):
    """回答オプションを表示する関数"""
    speaker = conversation.get("speaker", "")
    # st.write(f"この対話に続く{speaker}の応答として、どちらがより自然か評価してください。")
    # st.write(f"この対話に続く{speaker}の応答について、どちらの応答によりキャラクター情報が反映されているか評価してください。")
    st.write(f"この対話に続く{speaker}の応答として、どちらが正解応答により近いか評価してください。")

    model_a, model_b = model_pair
    response_a = find_response_for_context(model_responses[model_a], page)
    response_b = find_response_for_context(model_responses[model_b], page)
    
    # モデルの応答を表示
    col1, col2 = st.columns(2)
    
    with col1:
        display_model_response(response_a, f"モデルA", "lightblue")
    
    with col2:
        display_model_response(response_b, f"モデルB", "lightgreen")
    
    # 評価オプション
    options = [
        {"key": "model_a", "label": f"🟦モデルA"},
        {"key": "model_b", "label": f"🟩モデルB"},
        {"key": "tie", "label": "引き分け"}
    ]
    
    # 選択肢の表示
    st.markdown("**評価を選択してください：**")
    cols = st.columns(len(options))
    
    for i, option in enumerate(options):
        with cols[i]:
            choice_key = f"{option['key']}_{page}_{model_a}_{model_b}"
            st.checkbox(
                option["label"],
                key=choice_key,
                value=st.session_state.evaluations.get((page, model_a, model_b)) == option["key"],
                on_change=lambda k=option["key"], p=page, ma=model_a, mb=model_b: update_evaluation(p, ma, mb, k)
            )

def find_response_for_context(model_data, context_index):
    """特定のコンテキストに対するモデルの応答を見つける"""
    if context_index < len(model_data):
        return model_data[context_index].get("output", "応答データがありません")
    return "このコンテキストに対する応答がありません"

def display_navigation_controls(page, page_count, model_pairs):
    """ナビゲーションコントロールを表示する関数"""

    # 現在のモデルペアが何パターン目か表示
    pair_index = st.session_state.model_pair_index + 1
    total_pairs = len(model_pairs)
    
    
    # モデルペア切り替えボタン
    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("前のモデルペア", 
                 key="prev_pair", 
                 disabled=st.session_state.model_pair_index <= 0,
                 on_click=prev_model_pair)
        
    with col2:
        st.markdown(f"**モデルペア: {pair_index} / {total_pairs}**")
    
    with col3:
        st.button("次のモデルペア", 
                 key="next_pair", 
                 disabled=st.session_state.model_pair_index >= len(model_pairs) - 1,
                 on_click=next_model_pair)
        
    nav_col1, nav_col2, nav_col3 = st.columns(3)

    with nav_col1:
        st.button("前の対話", 
                 key="prev_button", 
                 disabled=page <= 0,
                 on_click=prev_page)
    
    with nav_col2:
        st.write(f"対話: {page + 1} / {page_count}")
    
    with nav_col3:
        st.button("次の対話", 
                 key="next_button", 
                 disabled=page >= page_count - 1,
                 on_click=next_page)
    
    # 送信ボタン
    all_evaluated = check_all_evaluated(model_pairs, page_count)
    user_id_provided = bool(st.session_state.get("user_id", "").strip())
    
    if not user_id_provided and all_evaluated:
        st.warning("評価を送信するにはユーザーIDを入力してください")
    
    st.button(
        "評価を送信", 
        key="submit_button", 
        disabled=not all_evaluated or not user_id_provided, 
        on_click=submit_evaluations
    )

    # 送信済みの場合、成功メッセージを表示
    if st.session_state.get("submitted", False):
        st.success("評価が送信されました！")
    
    # 評価の進捗状況
    display_evaluation_progress(model_pairs, page_count)

def display_evaluation_progress(model_pairs, page_count):
    """評価の進捗状況を表示"""
    total_comparisons = len(model_pairs) * page_count
    completed_comparisons = len(st.session_state.evaluations)
    progress = completed_comparisons / total_comparisons if total_comparisons > 0 else 0
    
    st.progress(progress)
    st.write(f"評価の進捗: {completed_comparisons}/{total_comparisons} ({progress*100:.1f}%)")

def display_reference_info(persona_data, conversation):
    """正解応答を固定表示する関数"""
    
    # st_fixed_containerでラップする
    with st_fixed_container(mode="fixed", position="top", border=True, key="persona_info"):
        title = conversation.get("title", "")
        name = conversation.get("speaker", "")
        gold_response = conversation.get("response", "")

        # persona_dataからtitleとspeakerに基づいてインデックスを取得
        context_indices = []
        for i, persona in enumerate(persona_data):
            if persona.get("title") == title and persona.get("name") == name:
                context_indices.append(i)
        
        if not context_indices:
            st.markdown("このコンテキストに対する正解情報がありません")
            return
        else:
            descriptions = [f'・ {persona_data[i].get("persona", "")}' for i in context_indices]

            st.markdown("### キャラクター情報")
            st.markdown(f"**名前**: {name}")
            st.markdown(f"**正解応答**:")
            st.markdown(create_rounded_box(gold_response, bg_color="sandybrown",), unsafe_allow_html=True)


def check_all_evaluated(model_pairs, page_count):
    """すべての評価が完了したかチェック"""
    total_comparisons = len(model_pairs) * page_count
    completed_comparisons = len(st.session_state.evaluations)
    return completed_comparisons == total_comparisons

# ------------------------------
# 状態管理関数
# ------------------------------
def update_evaluation(page, model_a, model_b, selected_option):
    """選択肢を更新する関数"""
    # 他の選択肢をクリア
    options = ["model_a", "model_b", "tie"]
    for opt in options:
        if opt != selected_option:
            choice_key = f"{opt}_{page}_{model_a}_{model_b}"
            if choice_key in st.session_state:
                st.session_state[choice_key] = False
    
    # 評価を更新
    if st.session_state.get(f"{selected_option}_{page}_{model_a}_{model_b}", False):
        st.session_state.evaluations[(page, model_a, model_b)] = selected_option
    else:
        st.session_state.evaluations.pop((page, model_a, model_b), None)

def next_page():
    """次のページに進む"""
    if st.session_state.page < st.session_state.page_count - 1:
        st.session_state.page += 1
        st.session_state.model_pair_index = 0  # モデルペアを最初にリセット

def prev_page():
    """前のページに戻る"""
    if st.session_state.page > 0:
        st.session_state.page -= 1
        st.session_state.model_pair_index = 0  # モデルペアを最初にリセット

def next_model_pair():
    """次のモデルペアに進む"""
    if st.session_state.model_pair_index < len(st.session_state.model_pairs) - 1:
        st.session_state.model_pair_index += 1

def prev_model_pair():
    """前のモデルペアに戻る"""
    if st.session_state.model_pair_index > 0:
        st.session_state.model_pair_index -= 1

def update_page_from_selector():
    """セレクトボックスからページを更新する関数"""
    st.session_state.page = st.session_state.page_selector - 1
    st.session_state.model_pair_index = 0  # モデルペアを最初にリセット

def submit_evaluations():
    """評価結果を保存する"""
    # ユーザーIDのチェック
    if not st.session_state.user_id.strip():
        st.error("評価を送信するにはユーザーIDを入力してください")
        return False
        
    # 評価データを変換
    evaluation_results = {
        "user_id": st.session_state.user_id,  # ユーザーIDを追加
        "timestamp": str(datetime.datetime.now(JST)),  # タイムスタンプを追加
        "evaluations": {}
    }
    
    for (page, model_a, model_b), choice in st.session_state.evaluations.items():
        key = f"{page}_{model_a}_vs_{model_b}"
        winner = model_a if choice == "model_a" else model_b if choice == "model_b" else "tie"
        
        # サンプリング前の元インデックスを取得
        original_index = st.session_state["sampled_indices"][page] if page < len(st.session_state["sampled_indices"]) else -1
        
        evaluation_results["evaluations"][key] = {
            "page": page,
            "original_index": original_index,  # 元のインデックスを追加
            "model_a": model_a,
            "model_b": model_b,
            "winner": winner
        }
    
    print("評価結果集計完了")
    # Google Sheetsに保存を試みる
    result = save_to_google_sheets(evaluation_results)
    
    if result:
        st.session_state["submitted"] = True
    return result

def generate_model_pairs(models):
    """利用可能なすべてのモデルペアを生成"""
    pairs = []
    for i in range(len(models)):
        for j in range(i+1, len(models)):
            pairs.append((models[i], models[j]))
    random.shuffle(pairs)  # ペアをランダムに並び替え
    return pairs

# ------------------------------
# メイン処理
# ------------------------------
def initialize_app():
    """アプリケーションの初期化"""
    st.set_page_config(layout="wide", page_title="LLMモデル評価アプリ")
    
    # セッションの初期化
    if "page" not in st.session_state:
        st.session_state["page"] = 0
    if "evaluations" not in st.session_state:
        st.session_state["evaluations"] = {}
    if "model_pairs" not in st.session_state:
        st.session_state["model_pairs"] = generate_model_pairs(AVAILABLE_MODELS)
    if "model_pair_index" not in st.session_state:
        st.session_state["model_pair_index"] = 0
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = ""
    
    # データの読み込み
    model_responses = load_model_responses()
    persona_data = load_persona_data()
    full_test_data = load_seen_test_data()
    
    # サンプル数を設定
    min_samples = min([len(responses) for responses in model_responses.values()])
    if min_samples == 0:
        st.error("モデル応答データが読み込めません。")
        return None, None, None, None
    
    # サンプリングされたテストデータが既にセッションにあるか確認
    if "sampled_test_data" not in st.session_state or "sampled_indices" not in st.session_state:
        # ランダムにサンプリングし、選択されたインデックスも保存
        indices = random.sample(range(min(len(full_test_data), min_samples)), min(SAMPLE_SIZE, min(len(full_test_data), min_samples)))
        st.session_state["sampled_indices"] = indices
        st.session_state["sampled_test_data"] = [full_test_data[i] for i in indices]
        
        # モデル応答もサンプリングされたインデックスに合わせてフィルタリング
        sampled_responses = {}
        for model_name, responses in model_responses.items():
            sampled_responses[model_name] = [responses[i] for i in indices]
        st.session_state["sampled_model_responses"] = sampled_responses
    
    # サンプリングデータのページ数を設定
    sampled_data = st.session_state["sampled_test_data"]
    sampled_responses = st.session_state["sampled_model_responses"]
    st.session_state.page_count = len(sampled_data)
    
    return sampled_responses, persona_data, sampled_data, st.session_state.model_pairs

def main():
    """メイン関数"""
    model_responses, persona_data, sampled_test_data, model_pairs = initialize_app()
    if not model_responses:
        return
    
    st.title("モデル応答評価用インターフェース")
    
    # ユーザーID入力欄の追加
    st.sidebar.markdown("### ユーザー情報")
    user_id = st.sidebar.text_input(
        "ユーザーID", 
        value=st.session_state.get("user_id", ""),
        key="input_user_id",
        placeholder="評価者IDを入力してください"
    )
    # ユーザーIDをセッションに保存
    st.session_state.user_id = user_id

    # サンプル数の表示（編集不可）
    st.sidebar.info(f"評価対象対話数: {len(sampled_test_data)}")
    
    # サイドバーのページセレクター
    st.sidebar.markdown("### ページ移動")
    page_count = st.session_state.page_count
    selected_page = st.sidebar.selectbox(
        "対話を選択", 
        range(1, page_count + 1), 
        index=st.session_state.page,
        key="page_selector",
        on_change=update_page_from_selector
    )
    
    # モデルペアセレクター
    # 実際のモデル名は表示しない
    # model_pair_names = [f"{a} vs {b}" for a, b in model_pairs]
    hidden_model_pairs_names = [f"ペア{i}" for i in range(1, len(model_pairs) + 1)]
    st.sidebar.selectbox(
        "モデルペアを選択",
        hidden_model_pairs_names,
        index=st.session_state.model_pair_index,
        key="model_pair_selector",
        on_change=lambda: setattr(st.session_state, "model_pair_index", 
                                hidden_model_pairs_names.index(st.session_state.model_pair_selector))
    )
    
    page = st.session_state.page
    current_model_pair = model_pairs[st.session_state.model_pair_index]
    
    # レイアウト
    context_col, persona_col = st.columns([2, 1])
    
    with context_col:
        # テストデータの表示
        if sampled_test_data and page < len(sampled_test_data):
            display_conversation(sampled_test_data[page])

        # モデル応答の表示と評価
        display_response_options(page, current_model_pair, model_responses, sampled_test_data[page])
        
        # ナビゲーションコントロールの表示
        display_navigation_controls(page, page_count, model_pairs)
    
    # ペルソナ情報の表示
    with persona_col:
        display_reference_info(persona_data, sampled_test_data[page])


if __name__ == "__main__":
    main()