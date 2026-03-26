#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import cgi
import cgitb

# libフォルダをsys.pathの先頭に追加
lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lib')
sys.path.insert(0, lib_path)

cgitb.enable()

from collections import Counter
import itertools
import re


def output_headers():
    print("Content-Type: application/json; charset=UTF-8")
    print("Access-Control-Allow-Origin: *")
    print("Access-Control-Allow-Methods: POST, OPTIONS")
    print("Access-Control-Allow-Headers: Content-Type")
    print()


def output_error(message):
    output_headers()
    print(json.dumps({"error": message}, ensure_ascii=False))


def tokenize(text, pos_filter, stopwords):
    """janomeで形態素解析し、指定品詞・ストップワードでフィルタリングして単語リストを返す"""
    try:
        from janome.tokenizer import Tokenizer
    except ImportError:
        raise RuntimeError("janomeがインストールされていません。libフォルダを確認してください。")

    t = Tokenizer()
    tokens = []
    for token in t.tokenize(text):
        part_of_speech = token.part_of_speech.split(',')[0]
        surface = token.surface
        base_form = token.base_form if token.base_form != '*' else surface

        if pos_filter and part_of_speech not in pos_filter:
            continue
        if stopwords and (surface in stopwords or base_form in stopwords):
            continue
        # 記号・空白・数字のみは除外
        if not re.search(r'[^\s\d\W]', surface, re.UNICODE):
            continue
        # 1文字の語は除外（ノイズになりやすい）
        if len(surface) < 2 and part_of_speech not in ['動詞', '形容詞']:
            continue

        tokens.append(base_form if base_form != '*' else surface)

    return tokens


def split_sentences(text):
    """テキストを文単位に分割する"""
    # 句点・改行・感嘆符・疑問符で分割
    sentences = re.split(r'[。！？\n]+', text)
    return [s.strip() for s in sentences if s.strip()]


def tokenize_sentence(sentence, pos_filter, stopwords):
    """1文を形態素解析してトークンリストを返す"""
    try:
        from janome.tokenizer import Tokenizer
    except ImportError:
        raise RuntimeError("janomeがインストールされていません。")

    t = Tokenizer()
    tokens = []
    for token in t.tokenize(sentence):
        part_of_speech = token.part_of_speech.split(',')[0]
        surface = token.surface
        base_form = token.base_form if token.base_form != '*' else surface

        if pos_filter and part_of_speech not in pos_filter:
            continue
        if stopwords and (surface in stopwords or base_form in stopwords):
            continue
        if not re.search(r'[^\s\d\W]', surface, re.UNICODE):
            continue
        if len(surface) < 2 and part_of_speech not in ['動詞', '形容詞']:
            continue

        tokens.append(base_form if base_form != '*' else surface)

    return tokens


def build_wordcloud(text, pos_filter, stopwords):
    """ワードクラウド用データを生成"""
    tokens = tokenize(text, pos_filter, stopwords)
    counter = Counter(tokens)
    top50 = counter.most_common(50)
    words = [{"text": word, "value": count} for word, count in top50]
    return {"words": words}


def build_network(text, pos_filter, stopwords):
    """共起ネットワーク用データを生成（文単位）"""
    sentences = split_sentences(text)

    word_counter = Counter()
    cooccurrence_counter = Counter()

    for sentence in sentences:
        tokens = tokenize_sentence(sentence, pos_filter, stopwords)
        unique_tokens = list(set(tokens))
        word_counter.update(tokens)
        # 全組み合わせで共起カウント
        for pair in itertools.combinations(sorted(unique_tokens), 2):
            cooccurrence_counter[pair] += 1

    # 上位50語に絞る
    top50_words = {word for word, _ in word_counter.most_common(50)}

    nodes = [
        {"id": word, "count": count}
        for word, count in word_counter.most_common(50)
    ]

    links = []
    for (source, target), value in cooccurrence_counter.most_common():
        if source in top50_words and target in top50_words and value > 0:
            links.append({"source": source, "target": target, "value": value})
        if len(links) >= 100:
            break

    return {"nodes": nodes, "links": links}


def main():
    method = os.environ.get('REQUEST_METHOD', 'GET').upper()

    # OPTIONSプリフライト対応
    if method == 'OPTIONS':
        output_headers()
        return

    if method != 'POST':
        output_error("POSTメソッドのみ受け付けます")
        return

    try:
        content_length = int(os.environ.get('CONTENT_LENGTH', 0))
        if content_length <= 0:
            output_error("リクエストボディが空です")
            return

        raw_body = sys.stdin.buffer.read(content_length).decode('utf-8')
        data = json.loads(raw_body)
    except (ValueError, json.JSONDecodeError) as e:
        output_error("JSONのパースに失敗しました: " + str(e))
        return
    except Exception as e:
        output_error("リクエスト読み込みエラー: " + str(e))
        return

    text = data.get("text", "").strip()
    if not text:
        output_error("テキストが入力されていません")
        return

    mode = data.get("mode", "wordcloud")
    pos_filter = data.get("pos", ["名詞", "動詞", "形容詞"])
    stopwords_raw = data.get("stopwords", [])

    # ストップワードは文字列リストとして扱う
    if isinstance(stopwords_raw, list):
        stopwords = set(stopwords_raw)
    else:
        stopwords = set()

    try:
        if mode == "wordcloud":
            result = build_wordcloud(text, pos_filter, stopwords)
        elif mode == "network":
            result = build_network(text, pos_filter, stopwords)
        else:
            output_error("不明なモード: " + mode)
            return
    except RuntimeError as e:
        output_error(str(e))
        return
    except Exception as e:
        output_error("解析エラー: " + str(e))
        return

    output_headers()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
