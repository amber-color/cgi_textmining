#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日本語テキストマイニング CGI

GET  → HTML画面を返す（d3.min.js・d3.layout.cloud.min.js をインライン埋め込み）
POST → 形態素解析結果を JSON で返す
"""

import sys
import os
import json
import cgitb
import re
import itertools
from collections import Counter

# Windows CGI環境でstdinをバイナリモードに設定
if sys.platform == 'win32':
    import msvcrt
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

# lib フォルダをsys.pathの先頭に追加
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_BASE, 'lib'))

cgitb.enable()


# ===========================================================================
# 形態素解析
# ===========================================================================

def _tokenize(text, pos_filter, stopwords):
    from janome.tokenizer import Tokenizer
    t = Tokenizer()
    result = []
    for token in t.tokenize(text):
        pos     = token.part_of_speech.split(',')[0]
        surface = token.surface
        base    = token.base_form if token.base_form not in ('*', '') else surface
        if pos_filter and pos not in pos_filter:
            continue
        if stopwords and (surface in stopwords or base in stopwords):
            continue
        if not re.search(r'[^\s\d\W]', surface, re.UNICODE):
            continue
        if len(surface) < 2 and pos not in ('動詞', '形容詞'):
            continue
        result.append(base)
    return result


def _split_sentences(text):
    return [s.strip() for s in re.split(r'[。！？\n]+', text) if s.strip()]


def build_wordcloud(text, pos_filter, stopwords):
    tokens  = _tokenize(text, pos_filter, stopwords)
    counter = Counter(tokens)
    return {"words": [{"text": w, "value": c} for w, c in counter.most_common(50)]}


def build_network(text, pos_filter, stopwords):
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
# HTML テンプレート（d3 は __D3JS__ / __CLOUDJS__ に置換して埋め込む）
# ===========================================================================

_HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>日本語テキストマイニング</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', 'Meiryo', 'Hiragino Sans', sans-serif;
       background: #f0f2f5; color: #333; min-height: 100vh; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
header { background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
         color: #fff; padding: 18px 24px; box-shadow: 0 2px 8px rgba(0,0,0,.15); }
header h1 { font-size: 1.6rem; font-weight: 700; letter-spacing: .05em; }
header p  { font-size: .85rem; opacity: .8; margin-top: 4px; }
.card { background: #fff; border-radius: 10px;
        box-shadow: 0 2px 12px rgba(0,0,0,.08); padding: 24px; margin-bottom: 20px; }
.card h2 { font-size: 1rem; color: #555; margin-bottom: 14px;
           padding-bottom: 8px; border-bottom: 2px solid #e8eaf0; }
.controls { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
@media (max-width: 640px) { .controls { grid-template-columns: 1fr; } }
.control-group label { display: block; font-size: .85rem; font-weight: 600;
                       color: #555; margin-bottom: 6px; }
textarea#inputText { width: 100%; height: 140px; padding: 10px 12px;
  border: 1px solid #dde1e8; border-radius: 6px; font-size: .95rem;
  font-family: inherit; resize: vertical; transition: border-color .2s; line-height: 1.6; }
textarea#inputText:focus { outline: none; border-color: #3498db;
  box-shadow: 0 0 0 3px rgba(52,152,219,.15); }
input[type="text"] { width: 100%; padding: 8px 12px; border: 1px solid #dde1e8;
  border-radius: 6px; font-size: .9rem; font-family: inherit; transition: border-color .2s; }
input[type="text"]:focus { outline: none; border-color: #3498db;
  box-shadow: 0 0 0 3px rgba(52,152,219,.15); }
.mode-buttons { display: flex; gap: 8px; }
.mode-btn { flex: 1; padding: 9px 12px; border: 2px solid #dde1e8; border-radius: 6px;
  background: #f8f9fc; color: #666; font-size: .9rem; font-weight: 600;
  cursor: pointer; transition: all .2s; text-align: center; }
.mode-btn:hover  { border-color: #3498db; color: #3498db; background: #eaf4fd; }
.mode-btn.active { border-color: #3498db; background: #3498db; color: #fff; }
.checkbox-group { display: flex; gap: 14px; flex-wrap: wrap; }
.checkbox-group label { display: flex; align-items: center; gap: 5px;
  font-size: .9rem; cursor: pointer; color: #555; font-weight: 500; }
.checkbox-group input[type="checkbox"] { width: 15px; height: 15px;
  accent-color: #3498db; cursor: pointer; }
.btn-analyze { display: block; width: 100%; padding: 12px;
  background: linear-gradient(135deg, #3498db, #2980b9); color: #fff;
  border: none; border-radius: 8px; font-size: 1rem; font-weight: 700;
  cursor: pointer; letter-spacing: .08em; transition: all .2s;
  box-shadow: 0 2px 8px rgba(52,152,219,.3); }
.btn-analyze:hover    { background: linear-gradient(135deg, #2980b9, #1f6fa3);
  box-shadow: 0 4px 14px rgba(52,152,219,.4); transform: translateY(-1px); }
.btn-analyze:active   { transform: translateY(0); }
.btn-analyze:disabled { background: #aab0bb; cursor: not-allowed;
  transform: none; box-shadow: none; }
#loading { display: none; align-items: center; justify-content: center;
  gap: 10px; padding: 16px; color: #3498db; font-size: .95rem; }
#loading.visible { display: flex; }
.spinner { width: 22px; height: 22px; border: 3px solid #d0e8fa;
  border-top-color: #3498db; border-radius: 50%;
  animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
#result-area { min-height: 460px; position: relative; }
#result-placeholder { display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 460px; color: #b0b8c8;
  font-size: .95rem; gap: 12px; }
#result-placeholder svg { opacity: .3; }
#error-msg { display: none; background: #fef2f2; border: 1px solid #fca5a5;
  color: #b91c1c; padding: 12px 16px; border-radius: 8px; font-size: .9rem; }
#viz-container { display: none; width: 100%; }
#viz-container.visible { display: block; }
#wordcloud-svg, #network-svg { display: block; width: 100%;
  border-radius: 8px; background: #fafbfd; }
.tooltip { position: absolute; background: rgba(30,40,60,.88); color: #fff;
  padding: 6px 12px; border-radius: 6px; font-size: .82rem;
  pointer-events: none; opacity: 0; transition: opacity .15s; z-index: 100; }
#stats { display: none; font-size: .82rem; color: #888;
  margin-top: 10px; text-align: right; }
#stats.visible { display: block; }
</style>
</head>
<body>

<header>
  <h1>日本語テキストマイニング</h1>
  <p>テキストを入力して形態素解析・可視化します</p>
</header>

<div class="container">

  <div class="card">
    <h2>テキスト入力</h2>
    <div class="control-group" style="margin-bottom:16px;">
      <label for="inputText">分析対象テキスト</label>
      <textarea id="inputText"
        placeholder="ここに分析したい日本語テキストを入力してください。&#10;複数の文を入力すると共起ネットワーク分析の精度が上がります。"></textarea>
    </div>

    <div class="controls">
      <div class="control-group">
        <label>表示モード</label>
        <div class="mode-buttons">
          <button class="mode-btn active" data-mode="wordcloud" onclick="setMode('wordcloud')">ワードクラウド</button>
          <button class="mode-btn"        data-mode="network"   onclick="setMode('network')">共起ネットワーク</button>
        </div>
      </div>

      <div class="control-group">
        <label>対象品詞</label>
        <div class="checkbox-group">
          <label><input type="checkbox" id="pos-noun" value="名詞" checked> 名詞</label>
          <label><input type="checkbox" id="pos-verb" value="動詞"> 動詞</label>
          <label><input type="checkbox" id="pos-adj"  value="形容詞"> 形容詞</label>
        </div>
      </div>

      <div class="control-group" style="grid-column: 1 / -1;">
        <label for="stopwords">ストップワード（カンマ区切り）</label>
        <input type="text" id="stopwords" placeholder="例: する, ある, なる, いる, こと, もの">
      </div>
    </div>

    <button class="btn-analyze" onclick="analyze()" id="analyzeBtn">分析を実行</button>

    <div id="loading">
      <div class="spinner"></div>
      <span>形態素解析中...</span>
    </div>
  </div>

  <div class="card">
    <h2 id="result-title">分析結果</h2>
    <div id="error-msg"></div>
    <div id="result-area">
      <div id="result-placeholder">
        <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"
             viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <path d="M3 9h18M9 21V9"/>
        </svg>
        <span>テキストを入力して「分析を実行」ボタンを押してください</span>
      </div>
      <div id="viz-container">
        <svg id="wordcloud-svg" style="display:none;"></svg>
        <svg id="network-svg"   style="display:none;"></svg>
      </div>
    </div>
    <div id="stats"></div>
  </div>

</div>

<div class="tooltip" id="tooltip"></div>

<script>
__D3JS__
</script>
<script>
__CLOUDJS__
</script>

<script>
// ===== 状態管理 =====
let currentMode = 'wordcloud';
// 自分自身のURLにPOSTする
const CGI_URL = window.location.pathname;

// ===== モード切替 =====
function setMode(mode) {
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
}

// ===== ストップワード解析 =====
function getStopwords() {
  return document.getElementById('stopwords').value
    .split(',').map(s => s.trim()).filter(s => s.length > 0);
}

// ===== 選択品詞取得 =====
function getPos() {
  return Array.from(
    document.querySelectorAll('.checkbox-group input[type="checkbox"]:checked')
  ).map(cb => cb.value);
}

// ===== 分析実行 =====
async function analyze() {
  const text = document.getElementById('inputText').value.trim();
  if (!text) { showError('テキストを入力してください。'); return; }

  const pos = getPos();
  if (pos.length === 0) { showError('対象品詞を1つ以上選択してください。'); return; }

  setLoading(true);
  hideError();
  hideViz();

  try {
    const response = await fetch(CGI_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=UTF-8' },
      body: JSON.stringify({ text, mode: currentMode, pos, stopwords: getStopwords() }),
      redirect: 'error'
    });

    if (!response.ok) {
      showError('サーバーエラー: HTTP ' + response.status + ' ' + response.statusText);
      return;
    }

    const data = await response.json();
    if (data.error) { showError('エラー: ' + data.error); return; }

    if (currentMode === 'wordcloud') renderWordcloud(data);
    else                             renderNetwork(data);

  } catch (e) {
    if (e instanceof TypeError && e.message.includes('redirect')) {
      showError('CGIへのリクエストがリダイレクトされました。サーバーのURL設定を確認してください。');
    } else {
      showError('通信エラーが発生しました: ' + e.message);
    }
  } finally {
    setLoading(false);
  }
}

// ===== UI制御 =====
function setLoading(flag) {
  document.getElementById('loading').classList.toggle('visible', flag);
  document.getElementById('analyzeBtn').disabled = flag;
}
function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg; el.style.display = 'block';
}
function hideError() { document.getElementById('error-msg').style.display = 'none'; }
function hideViz() {
  document.getElementById('result-placeholder').style.display = 'flex';
  document.getElementById('viz-container').classList.remove('visible');
  document.getElementById('wordcloud-svg').style.display = 'none';
  document.getElementById('network-svg').style.display = 'none';
  document.getElementById('stats').classList.remove('visible');
}
function showViz(svgId) {
  document.getElementById('result-placeholder').style.display = 'none';
  document.getElementById('viz-container').classList.add('visible');
  document.getElementById('wordcloud-svg').style.display = svgId === 'wordcloud-svg' ? 'block' : 'none';
  document.getElementById('network-svg').style.display   = svgId === 'network-svg'   ? 'block' : 'none';
}

// ===== ワードクラウド描画 =====
function renderWordcloud(data) {
  const words = data.words || [];
  if (words.length === 0) {
    showError('単語が抽出されませんでした。テキストや品詞設定を確認してください。');
    return;
  }
  const svg = d3.select('#wordcloud-svg');
  svg.selectAll('*').remove();
  const W = svg.node().parentElement.clientWidth || 800;
  const H = 460;
  svg.attr('width', W).attr('height', H);

  const maxVal = d3.max(words, d => d.value);
  const minVal = d3.min(words, d => d.value);
  const fontScale = d3.scaleLinear().domain([minVal, maxVal]).range([14, Math.min(80, W / 8)]);
  const palette = [
    '#e74c3c','#e67e22','#f39c12','#2ecc71','#1abc9c',
    '#3498db','#2980b9','#9b59b6','#8e44ad','#e91e63',
    '#00bcd4','#4caf50','#ff5722','#607d8b','#795548'
  ];
  const colorScale = d3.scaleOrdinal(palette);

  d3.layout.cloud()
    .size([W, H])
    .words(words.map(d => ({ text: d.text, size: fontScale(d.value), value: d.value })))
    .padding(5)
    .rotate(() => Math.random() < 0.7 ? 0 : 90)
    .font('sans-serif')
    .fontSize(d => d.size)
    .on('end', cloudWords => {
      const g = svg.append('g').attr('transform', `translate(${W/2},${H/2})`);
      const tip = document.getElementById('tooltip');
      g.selectAll('text').data(cloudWords).enter().append('text')
        .style('font-family', 'sans-serif')
        .style('font-size',   d => d.size + 'px')
        .style('fill',        (d, i) => colorScale(i))
        .style('cursor',      'default')
        .attr('text-anchor',  'middle')
        .attr('transform',    d => `translate(${d.x},${d.y}) rotate(${d.rotate})`)
        .text(d => d.text)
        .on('mousemove', (event, d) => {
          tip.style.opacity = '1';
          tip.style.left = (event.pageX + 12) + 'px';
          tip.style.top  = (event.pageY - 28) + 'px';
          tip.textContent = `${d.text}: ${d.value}回`;
        })
        .on('mouseleave', () => { tip.style.opacity = '0'; });
    })
    .start();

  showViz('wordcloud-svg');
  const stats = document.getElementById('stats');
  stats.textContent = `表示単語数: ${words.length} 語`;
  stats.classList.add('visible');
  document.getElementById('result-title').textContent = 'ワードクラウド';
}

// ===== 共起ネットワーク描画 =====
function renderNetwork(data) {
  const nodes = data.nodes || [];
  const links = data.links || [];
  if (nodes.length === 0) {
    showError('単語が抽出されませんでした。テキストや品詞設定を確認してください。');
    return;
  }
  const svg = d3.select('#network-svg');
  svg.selectAll('*').remove();
  const W = svg.node().parentElement.clientWidth || 800;
  const H = 520;
  svg.attr('width', W).attr('height', H);

  const maxCount = d3.max(nodes, d => d.count) || 1;
  const minCount = d3.min(nodes, d => d.count) || 1;
  const nodeRadius = d3.scaleLinear().domain([minCount, maxCount]).range([8, 32]);
  const maxLink = d3.max(links, d => d.value) || 1;
  const linkWidth = d3.scaleLinear().domain([1, maxLink]).range([1, 8]);
  const palette = [
    '#3498db','#e74c3c','#2ecc71','#9b59b6','#f39c12',
    '#1abc9c','#e67e22','#e91e63','#00bcd4','#8bc34a'
  ];
  const colorScale = d3.scaleOrdinal(palette);

  const zoom = d3.zoom().scaleExtent([0.3, 3])
    .on('zoom', event => g.attr('transform', event.transform));
  svg.call(zoom);
  const g = svg.append('g');

  const simulation = d3.forceSimulation(nodes)
    .force('link',      d3.forceLink(links).id(d => d.id).distance(d => 80 + 50 / (d.value || 1)).strength(0.6))
    .force('charge',    d3.forceManyBody().strength(-200))
    .force('center',    d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide().radius(d => nodeRadius(d.count) + 8));

  const link = g.append('g').selectAll('line').data(links).enter().append('line')
    .attr('stroke', '#aab8cc').attr('stroke-opacity', 0.6)
    .attr('stroke-width', d => linkWidth(d.value));

  const nodeG = g.append('g').selectAll('g').data(nodes).enter().append('g')
    .call(d3.drag()
      .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag',  (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end',   (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

  nodeG.append('circle')
    .attr('r', d => nodeRadius(d.count))
    .attr('fill', (d, i) => colorScale(i % palette.length))
    .attr('stroke', '#fff').attr('stroke-width', 2).style('cursor', 'grab');

  nodeG.append('text')
    .text(d => d.id)
    .attr('text-anchor', 'middle')
    .attr('dy', d => nodeRadius(d.count) + 13)
    .attr('font-size', d => Math.max(10, Math.min(14, nodeRadius(d.count) * 0.7)) + 'px')
    .attr('font-family', 'sans-serif').attr('fill', '#333').attr('pointer-events', 'none');

  const tip = document.getElementById('tooltip');
  nodeG
    .on('mousemove', (event, d) => {
      tip.style.opacity = '1';
      tip.style.left = (event.pageX + 12) + 'px';
      tip.style.top  = (event.pageY - 28) + 'px';
      tip.textContent = `${d.id}: ${d.count}回出現`;
    })
    .on('mouseleave', () => { tip.style.opacity = '0'; });

  simulation.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    nodeG.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  showViz('network-svg');
  const stats = document.getElementById('stats');
  stats.textContent = `ノード: ${nodes.length} 語 / エッジ: ${links.length} 本`;
  stats.classList.add('visible');
  document.getElementById('result-title').textContent = '共起ネットワーク';
}

// ===== Enterキーで実行（Shift+Enter改行） =====
document.getElementById('inputText').addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); analyze(); }
});
</script>
</body>
</html>"""


# ===========================================================================
# ハンドラ
# ===========================================================================

def _read_js(filename):
    path = os.path.join(_BASE, 'static', filename)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def serve_html():
    """GETリクエスト: HTMLページを返す"""
    d3    = _read_js('d3.min.js')
    cloud = _read_js('d3.layout.cloud.min.js')

    print("Content-Type: text/html; charset=UTF-8")
    print()

    if not d3 or not cloud:
        missing = []
        if not d3:    missing.append('static/d3.min.js')
        if not cloud: missing.append('static/d3.layout.cloud.min.js')
        print("<!DOCTYPE html><html lang='ja'><head><meta charset='UTF-8'>")
        print("<title>セットアップが必要です</title></head><body>")
        print("<h2>セットアップが必要です</h2>")
        print("<p>以下のファイルを配置してください:</p><ul>")
        for f in missing:
            print("<li><code>{}</code></li>".format(f))
        print("</ul></body></html>")
        return

    html = _HTML.replace('__D3JS__', d3).replace('__CLOUDJS__', cloud)
    print(html)


def serve_json_error(message):
    print("Content-Type: application/json; charset=UTF-8")
    print("Access-Control-Allow-Origin: *")
    print()
    print(json.dumps({"error": message}, ensure_ascii=False))


def serve_json(data):
    print("Content-Type: application/json; charset=UTF-8")
    print("Access-Control-Allow-Origin: *")
    print()
    print(json.dumps(data, ensure_ascii=False))


def handle_post():
    """POSTリクエスト: 形態素解析してJSONを返す"""
    try:
        length = int(os.environ.get('CONTENT_LENGTH', 0))
        if length <= 0:
            serve_json_error("リクエストボディが空です")
            return
        body = sys.stdin.buffer.read(length).decode('utf-8')
        req  = json.loads(body)
    except (ValueError, json.JSONDecodeError) as e:
        serve_json_error("JSONのパースに失敗しました: " + str(e))
        return
    except Exception as e:
        serve_json_error("リクエスト読み込みエラー: " + str(e))
        return

    text = req.get("text", "").strip()
    if not text:
        serve_json_error("テキストが入力されていません")
        return

    mode      = req.get("mode", "wordcloud")
    pos       = req.get("pos",  ["名詞", "動詞", "形容詞"])
    sw_raw    = req.get("stopwords", [])
    stopwords = set(sw_raw) if isinstance(sw_raw, list) else set()

    try:
        if mode == "wordcloud":
            result = build_wordcloud(text, pos, stopwords)
        elif mode == "network":
            result = build_network(text, pos, stopwords)
        else:
            serve_json_error("不明なモード: " + mode)
            return
    except ImportError:
        serve_json_error("janomeが見つかりません。lib/フォルダにjanomeを配置してください。")
        return
    except Exception as e:
        serve_json_error("解析エラー: " + str(e))
        return

    serve_json(result)


# ===========================================================================
# エントリーポイント
# ===========================================================================

def main():
    method = os.environ.get('REQUEST_METHOD', '').upper()

    if method == 'OPTIONS':
        print("Content-Type: text/plain")
        print("Access-Control-Allow-Origin: *")
        print("Access-Control-Allow-Methods: GET, POST, OPTIONS")
        print("Access-Control-Allow-Headers: Content-Type")
        print()
        return

    if method in ('GET', ''):
        serve_html()
        return

    if method == 'POST':
        handle_post()
        return

    serve_json_error("未対応のメソッド: " + method)


if __name__ == '__main__':
    main()
