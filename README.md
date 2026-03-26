# 日本語テキストマイニング CGI アプリ

PythonのCGIスクリプトとD3.jsを使った日本語テキストマイニングWebアプリです。

## ディレクトリ構成

```
cgi-bin/
  textmine.py             # メインCGIスクリプト（janomeで形態素解析 → JSON返却）
static/
  index.html              # フロントエンド（D3.js描画）
  d3.min.js               # D3.js v7（要配置）
  d3.layout.cloud.min.js  # d3-cloud（要配置）
  style.css
lib/
  janome/                 # janomeをwhlから解凍して配置
```

## セットアップ

### 1. janome の配置

```bash
pip install janome --target=lib/
```

### 2. D3.js の配置

- D3.js v7 の `d3.min.js` を `static/` に配置
- d3-cloud の `d3.layout.cloud.min.js` を `static/` に配置

### 3. CGIサーバー設定（Apache例）

```apache
ScriptAlias /cgi-bin/ /path/to/cgi-bin/
<Directory "/path/to/cgi-bin">
    Options +ExecCGI
    AddHandler cgi-script .py
</Directory>
```

### 4. パーミッション（Linux/Mac）

```bash
chmod +x cgi-bin/textmine.py
```

## 機能

- **ワードクラウド**: 単語の出現頻度をフォントサイズで表現（d3-cloud）
- **共起ネットワーク**: 文単位の共起関係をノード・エッジで表現（Force Simulation）
- 品詞フィルター（名詞・動詞・形容詞）
- ストップワード設定

## API 仕様

**POST** `/cgi-bin/textmine.py`

リクエスト:
```json
{
  "text": "分析対象テキスト",
  "mode": "wordcloud",
  "pos": ["名詞", "動詞"],
  "stopwords": ["する", "ある"]
}
```

レスポンス（wordcloudモード）:
```json
{"words": [{"text": "日本語", "value": 12}, ...]}
```

レスポンス（networkモード）:
```json
{
  "nodes": [{"id": "日本語", "count": 12}, ...],
  "links": [{"source": "日本語", "target": "分析", "value": 3}, ...]
}
```
