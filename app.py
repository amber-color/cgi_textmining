#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日本語テキストマイニング - デスクトップGUIアプリ

使い方:
  python app.py

必要ファイル:
  lib/janome/          ... janomeをwhlから解凍して配置
  static/d3.min.js     ... D3.js v7
  static/d3.layout.cloud.min.js ... d3-cloud
"""

import sys
import os
import json
import re
import csv
import threading
import webbrowser
import shutil
import tempfile
from collections import Counter
import itertools
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# lib をパスの先頭に追加
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_BASE_DIR, 'lib'))


# ===========================================================================
# 解析ロジック
# ===========================================================================

def _tokenize(text, pos_filter, stopwords):
    """janomeで形態素解析し、フィルタ済み基本形リストを返す"""
    from janome.tokenizer import Tokenizer
    t = Tokenizer()
    result = []
    for token in t.tokenize(text):
        pos = token.part_of_speech.split(',')[0]
        surface = token.surface
        base = token.base_form if token.base_form not in ('*', '') else surface

        if pos_filter and pos not in pos_filter:
            continue
        if stopwords and (surface in stopwords or base in stopwords):
            continue
        # 記号・数字のみの語を除外
        if not re.search(r'[^\s\d\W]', surface, re.UNICODE):
            continue
        # 1文字の名詞は除外（ノイズが多い）
        if len(surface) < 2 and pos not in ('動詞', '形容詞'):
            continue
        result.append(base)
    return result


def _split_sentences(text):
    return [s.strip() for s in re.split(r'[。！？\n]+', text) if s.strip()]


def build_wordcloud_data(text, pos_filter, stopwords):
    tokens = _tokenize(text, pos_filter, stopwords)
    counter = Counter(tokens)
    return {"words": [{"text": w, "value": c} for w, c in counter.most_common(50)]}


def build_network_data(text, pos_filter, stopwords):
    word_counter = Counter()
    pair_counter = Counter()

    for sentence in _split_sentences(text):
        tokens = _tokenize(sentence, pos_filter, stopwords)
        unique = list(set(tokens))
        word_counter.update(tokens)
        for pair in itertools.combinations(sorted(unique), 2):
            pair_counter[pair] += 1

    top50 = {w for w, _ in word_counter.most_common(50)}
    nodes = [{"id": w, "count": c} for w, c in word_counter.most_common(50)]
    links = []
    for (s, t), v in pair_counter.most_common():
        if s in top50 and t in top50:
            links.append({"source": s, "target": t, "value": v})
        if len(links) >= 100:
            break
    return {"nodes": nodes, "links": links}


# ===========================================================================
# 結果HTML生成
# ===========================================================================

_RESULT_HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>テキストマイニング結果</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Meiryo','Hiragino Sans',sans-serif;background:#f0f2f5;min-height:100vh}
header{background:linear-gradient(135deg,#2c3e50,#3498db);color:#fff;padding:16px 24px}
header h1{font-size:1.4rem;font-weight:700}
header p{font-size:.82rem;opacity:.8;margin-top:3px}
.card{background:#fff;border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,.08);margin:20px;padding:20px}
svg{display:block;width:100%;background:#fafbfd;border-radius:8px}
#stats{color:#888;font-size:.82rem;text-align:right;margin-top:8px}
.tooltip{position:fixed;background:rgba(30,40,60,.88);color:#fff;padding:6px 12px;
  border-radius:6px;font-size:.82rem;pointer-events:none;opacity:0;transition:opacity .15s;z-index:100}
</style>
</head>
<body>
<header>
  <h1 id="ttl">分析結果</h1>
  <p id="sub"></p>
</header>
<div class="card">
  <svg id="viz"></svg>
  <div id="stats"></div>
</div>
<div class="tooltip" id="tip"></div>
<script src="d3.min.js"></script>
<script src="d3.layout.cloud.min.js"></script>
<script>
const MODE = "__MODE__";
const DATA = __DATA__;

const W = Math.max(600, window.innerWidth - 80);
const H = Math.max(500, window.innerHeight - 180);
const svg = d3.select("#viz").attr("width", W).attr("height", H);
const tip = document.getElementById("tip");

function showTip(e, txt) {
  tip.style.opacity = "1";
  tip.style.left = (e.clientX + 12) + "px";
  tip.style.top  = (e.clientY - 28) + "px";
  tip.textContent = txt;
}
function hideTip() { tip.style.opacity = "0"; }

/* ---- ワードクラウド ---- */
if (MODE === "wordcloud") {
  document.getElementById("ttl").textContent = "ワードクラウド";
  const words = DATA.words || [];
  document.getElementById("stats").textContent = "表示単語数: " + words.length + " 語";
  document.getElementById("sub").textContent   = "単語の大きさ = 出現頻度";

  const maxV = d3.max(words, d => d.value) || 1;
  const minV = d3.min(words, d => d.value) || 1;
  const fScale = d3.scaleLinear().domain([minV, maxV]).range([14, Math.min(72, W / 8)]);
  const palette = [
    "#e74c3c","#e67e22","#f39c12","#2ecc71","#1abc9c",
    "#3498db","#2980b9","#9b59b6","#8e44ad","#e91e63",
    "#00bcd4","#4caf50","#ff5722","#607d8b","#795548"
  ];
  const cScale = d3.scaleOrdinal(palette);

  d3.layout.cloud()
    .size([W, H])
    .words(words.map(d => ({ text: d.text, size: fScale(d.value), value: d.value })))
    .padding(5)
    .rotate(() => Math.random() < 0.7 ? 0 : 90)
    .font("sans-serif")
    .fontSize(d => d.size)
    .on("end", function(cloudWords) {
      svg.append("g").attr("transform", "translate(" + W/2 + "," + H/2 + ")")
        .selectAll("text").data(cloudWords).enter().append("text")
          .style("font-family", "sans-serif")
          .style("font-size",   d => d.size + "px")
          .style("fill",        (d, i) => cScale(i))
          .attr("text-anchor",  "middle")
          .attr("transform",    d => "translate(" + d.x + "," + d.y + ") rotate(" + d.rotate + ")")
          .text(d => d.text)
          .on("mousemove",  (e, d) => showTip(e, d.text + ": " + d.value + "回"))
          .on("mouseleave", hideTip);
    })
    .start();

/* ---- 共起ネットワーク ---- */
} else {
  document.getElementById("ttl").textContent = "共起ネットワーク";
  document.getElementById("sub").textContent = "ノードサイズ = 出現頻度 / エッジの太さ = 共起頻度 / ドラッグで移動・スクロールでズーム";
  const nodes = DATA.nodes || [];
  const links = DATA.links || [];
  document.getElementById("stats").textContent =
    "ノード: " + nodes.length + " 語 / エッジ: " + links.length + " 本";

  const maxC = d3.max(nodes, d => d.count) || 1;
  const minC = d3.min(nodes, d => d.count) || 1;
  const rScale  = d3.scaleLinear().domain([minC, maxC]).range([8, 32]);
  const maxL = d3.max(links, d => d.value) || 1;
  const lwScale = d3.scaleLinear().domain([1, maxL]).range([1, 8]);
  const palette = [
    "#3498db","#e74c3c","#2ecc71","#9b59b6","#f39c12",
    "#1abc9c","#e67e22","#e91e63","#00bcd4","#8bc34a"
  ];
  const cScale = d3.scaleOrdinal(palette);

  const zoom = d3.zoom().scaleExtent([0.2, 4])
    .on("zoom", e => g.attr("transform", e.transform));
  svg.call(zoom);
  const g = svg.append("g");

  const sim = d3.forceSimulation(nodes)
    .force("link",      d3.forceLink(links).id(d => d.id)
                          .distance(d => 80 + 50 / (d.value || 1)).strength(0.6))
    .force("charge",    d3.forceManyBody().strength(-220))
    .force("center",    d3.forceCenter(W / 2, H / 2))
    .force("collision", d3.forceCollide().radius(d => rScale(d.count) + 8));

  const link = g.append("g").selectAll("line").data(links).enter().append("line")
    .attr("stroke", "#aab8cc").attr("stroke-opacity", 0.65)
    .attr("stroke-width", d => lwScale(d.value));

  const nodeG = g.append("g").selectAll("g").data(nodes).enter().append("g")
    .call(d3.drag()
      .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag",  (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on("end",   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

  nodeG.append("circle")
    .attr("r",            d => rScale(d.count))
    .attr("fill",         (d, i) => cScale(i % palette.length))
    .attr("stroke",       "#fff")
    .attr("stroke-width", 2)
    .style("cursor",      "grab");

  nodeG.append("text")
    .text(d => d.id)
    .attr("text-anchor", "middle")
    .attr("dy",          d => rScale(d.count) + 13)
    .attr("font-size",   d => Math.max(10, Math.min(14, rScale(d.count) * 0.7)) + "px")
    .attr("font-family", "sans-serif")
    .attr("fill",        "#333")
    .attr("pointer-events", "none");

  nodeG
    .on("mousemove",  (e, d) => showTip(e, d.id + ": " + d.count + "回出現"))
    .on("mouseleave", hideTip);

  sim.on("tick", () => {
    link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    nodeG.attr("transform", d => "translate(" + d.x + "," + d.y + ")");
  });
}
</script>
</body>
</html>"""


def _open_result_in_browser(data, mode):
    """結果HTMLを一時ディレクトリに生成してブラウザで開く"""
    tmp_dir = tempfile.mkdtemp(prefix="textmine_")

    # D3.jsをコピー
    static_dir = os.path.join(_BASE_DIR, 'static')
    for js in ('d3.min.js', 'd3.layout.cloud.min.js'):
        src = os.path.join(static_dir, js)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(tmp_dir, js))

    # HTMLに分析データを埋め込み
    html = _RESULT_HTML.replace("__MODE__", mode)
    html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    html_path = os.path.join(tmp_dir, "result.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    webbrowser.open('file:///' + html_path.replace('\\', '/'))


# ===========================================================================
# GUIアプリ
# ===========================================================================

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("日本語テキストマイニング")
        self.geometry("720x620")
        self.minsize(560, 500)
        self.configure(bg='#f0f2f5')
        self._build_style()
        self._build_ui()

    # ---- スタイル ----

    def _build_style(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('TFrame',       background='#f0f2f5')
        s.configure('TLabel',       background='#f0f2f5', font=('Meiryo', 9))
        s.configure('Head.TLabel',  background='#f0f2f5', font=('Meiryo', 9, 'bold'), foreground='#444')
        s.configure('Hint.TLabel',  background='#f0f2f5', font=('Meiryo', 8),         foreground='#aaa')
        s.configure('TCheckbutton', background='#f0f2f5', font=('Meiryo', 9))
        s.configure('TRadiobutton', background='#f0f2f5', font=('Meiryo', 9))
        s.configure('TLabelframe',        background='#f0f2f5')
        s.configure('TLabelframe.Label',  background='#f0f2f5', font=('Meiryo', 9, 'bold'), foreground='#555')
        s.configure('Run.TButton',  font=('Meiryo', 10, 'bold'), padding=(0, 9))

    # ---- UI構築 ----

    def _build_ui(self):
        # ヘッダー
        hdr = tk.Frame(self, bg='#2c3e50')
        hdr.pack(fill='x')
        tk.Label(hdr, text="日本語テキストマイニング",
                 bg='#2c3e50', fg='#ffffff', font=('Meiryo', 13, 'bold'),
                 padx=20, pady=10).pack(anchor='w')
        tk.Label(hdr, text="テキストまたはファイルを読み込んで形態素解析・可視化します",
                 bg='#2c3e50', fg='#90b8d0', font=('Meiryo', 8),
                 padx=20, pady=(0, 10)).pack(anchor='w')

        # メインコンテンツ
        body = ttk.Frame(self, padding=(14, 12, 14, 8))
        body.pack(fill='both', expand=True)

        # ---- 入力エリア ----
        in_frm = ttk.LabelFrame(body, text="テキスト入力", padding=(10, 6))
        in_frm.pack(fill='both', expand=True, pady=(0, 10))

        # ファイルボタン行
        btn_row = ttk.Frame(in_frm)
        btn_row.pack(fill='x', pady=(0, 6))
        ttk.Button(btn_row, text="TXT を開く",  command=self._open_txt).pack(side='left', padx=(0, 6))
        ttk.Button(btn_row, text="CSV を開く",  command=self._open_csv).pack(side='left', padx=(0, 6))
        ttk.Button(btn_row, text="クリア",       command=self._clear).pack(side='right')

        # テキストエリア
        self.text_area = scrolledtext.ScrolledText(
            in_frm, height=9, font=('Meiryo', 10), wrap='word',
            relief='flat', borderwidth=1,
            highlightbackground='#cdd1db', highlightthickness=1,
        )
        self.text_area.pack(fill='both', expand=True)

        # ---- オプション ----
        opt_frm = ttk.LabelFrame(body, text="オプション", padding=(10, 6))
        opt_frm.pack(fill='x', pady=(0, 10))

        row = ttk.Frame(opt_frm)
        row.pack(fill='x')

        # モード
        mc = ttk.Frame(row)
        mc.pack(side='left', padx=(0, 28), anchor='n')
        ttk.Label(mc, text="表示モード", style='Head.TLabel').pack(anchor='w', pady=(0, 3))
        self._mode = tk.StringVar(value='wordcloud')
        ttk.Radiobutton(mc, text="ワードクラウド",   variable=self._mode, value='wordcloud').pack(anchor='w')
        ttk.Radiobutton(mc, text="共起ネットワーク", variable=self._mode, value='network').pack(anchor='w')

        # 品詞
        pc = ttk.Frame(row)
        pc.pack(side='left', padx=(0, 28), anchor='n')
        ttk.Label(pc, text="対象品詞", style='Head.TLabel').pack(anchor='w', pady=(0, 3))
        self._noun = tk.BooleanVar(value=True)
        self._verb = tk.BooleanVar(value=False)
        self._adj  = tk.BooleanVar(value=False)
        ttk.Checkbutton(pc, text="名詞",   variable=self._noun).pack(anchor='w')
        ttk.Checkbutton(pc, text="動詞",   variable=self._verb).pack(anchor='w')
        ttk.Checkbutton(pc, text="形容詞", variable=self._adj).pack(anchor='w')

        # ストップワード
        sc = ttk.Frame(row)
        sc.pack(side='left', fill='x', expand=True, anchor='n')
        ttk.Label(sc, text="ストップワード（カンマ区切り）", style='Head.TLabel').pack(anchor='w', pady=(0, 3))
        self._sw = tk.StringVar()
        ttk.Entry(sc, textvariable=self._sw, font=('Meiryo', 9)).pack(fill='x')
        ttk.Label(sc, text="例: する, ある, なる, いる, こと, もの", style='Hint.TLabel').pack(anchor='w', pady=(2, 0))

        # ---- 実行ボタン ----
        self._run_btn = ttk.Button(body, text="分析を実行", style='Run.TButton',
                                   command=self._run)
        self._run_btn.pack(fill='x', pady=(0, 4))

        # ---- ステータスバー ----
        self._status = tk.StringVar(value="テキストを入力して「分析を実行」を押してください")
        tk.Label(self, textvariable=self._status,
                 bg='#dde1ea', fg='#555', font=('Meiryo', 8),
                 anchor='w', padx=12, pady=4).pack(fill='x', side='bottom')

    # ---- ファイル読み込み ----

    def _open_txt(self):
        path = filedialog.askopenfilename(
            title="TXTファイルを選択",
            filetypes=[("テキストファイル", "*.txt"), ("すべてのファイル", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            self.text_area.delete('1.0', 'end')
            self.text_area.insert('1.0', content)
            self._set_status("読み込み完了: " + os.path.basename(path))
        except Exception as e:
            messagebox.showerror("読み込みエラー", str(e))

    def _open_csv(self):
        path = filedialog.askopenfilename(
            title="CSVファイルを選択",
            filetypes=[("CSVファイル", "*.csv"), ("すべてのファイル", "*.*")]
        )
        if not path:
            return
        try:
            lines = []
            for enc in ('utf-8-sig', 'utf-8', 'cp932', 'shift_jis'):
                try:
                    with open(path, 'r', encoding=enc, newline='') as f:
                        for row in csv.reader(f):
                            text = ' '.join(c.strip() for c in row if c.strip())
                            if text:
                                lines.append(text)
                    break
                except (UnicodeDecodeError, csv.Error):
                    continue

            if not lines:
                messagebox.showwarning("警告", "CSVからテキストを読み込めませんでした。")
                return
            self.text_area.delete('1.0', 'end')
            self.text_area.insert('1.0', '\n'.join(lines))
            self._set_status("読み込み完了: {} ({} 行)".format(os.path.basename(path), len(lines)))
        except Exception as e:
            messagebox.showerror("読み込みエラー", str(e))

    def _clear(self):
        self.text_area.delete('1.0', 'end')
        self._set_status("クリアしました")

    # ---- 分析 ----

    def _run(self):
        text = self.text_area.get('1.0', 'end').strip()
        if not text:
            messagebox.showwarning("入力エラー", "テキストを入力してください。")
            return

        pos = []
        if self._noun.get(): pos.append('名詞')
        if self._verb.get(): pos.append('動詞')
        if self._adj.get():  pos.append('形容詞')
        if not pos:
            messagebox.showwarning("入力エラー", "対象品詞を1つ以上選択してください。")
            return

        sw       = set(s.strip() for s in self._sw.get().split(',') if s.strip())
        mode     = self._mode.get()

        self._run_btn.config(state='disabled')
        self._set_status("形態素解析中...")

        def task():
            try:
                if mode == 'wordcloud':
                    data = build_wordcloud_data(text, pos, sw)
                    count = len(data.get('words', []))
                else:
                    data = build_network_data(text, pos, sw)
                    count = len(data.get('nodes', []))

                if count == 0:
                    self.after(0, lambda: self._finish_error(
                        "単語が抽出されませんでした。\nテキストの内容や品詞・ストップワードの設定を確認してください。"
                    ))
                    return

                _open_result_in_browser(data, mode)
                self.after(0, lambda: self._finish_ok(count, mode))

            except ImportError:
                self.after(0, lambda: self._finish_error(
                    "janome が見つかりません。\nlib/ フォルダに janome を配置してください。"
                ))
            except Exception as e:
                self.after(0, lambda: self._finish_error("解析エラー: " + str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _finish_ok(self, count, mode):
        label = "ワードクラウド" if mode == 'wordcloud' else "共起ネットワーク"
        self._set_status("完了 — {} ({} 語) をブラウザで表示しました".format(label, count))
        self._run_btn.config(state='normal')

    def _finish_error(self, msg):
        messagebox.showerror("エラー", msg)
        self._set_status("エラーが発生しました")
        self._run_btn.config(state='normal')

    def _set_status(self, msg):
        self._status.set(msg)


# ===========================================================================
# エントリーポイント
# ===========================================================================

if __name__ == '__main__':
    app = App()
    app.mainloop()
