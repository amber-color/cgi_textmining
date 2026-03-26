# 日本語テキストマイニング CGI アプリ

PythonのCGIスクリプトとD3.jsを使った日本語テキストマイニングWebアプリです。

## ディレクトリ構成

```
cgi-bin/
  textmine.cgi        # メインCGIスクリプト（janomeで形態素解析 → JSON返却）
static/
  index.html          # フロントエンド（D3.js描画）
  d3.min.js           # D3.js v7（要配置）
  d3.layout.cloud.min.js  # d3-cloud（要配置）
  style.css
lib/
  janome/             # janomeをwhlから解凍して配置
```

## セットアップ

### 1. janomeの配置

```bash
# janomeのwhlをダウンロード後、lib/に解凍
pip download janome --no-deps -d ./wheels
cd lib
unzip ../wheels/janome-*.whl
```

または `pip install janome --target=lib/` でも可。

### 2. D3.jsの配置

- [D3.js v7](https://d3js.org/) から `d3.min.js` をダウンロードして `static/` に配置
- [d3-cloud](https://github.com/jasondavies/d3-cloud) から `d3.layout.cloud.min.js` をダウンロードして `static/` に配置

### 3. CGIサーバー設定（Apache例）

```apache
ScriptAlias /cgi-bin/ /path/to/cgi-bin/
<Directory "/path/to/cgi-bin">
    Options +ExecCGI
    AddHandler cgi-script .cgi
</Directory>
```

### 4. ファイルのパーミッション（Linux/Mac）

```bash
chmod +x cgi-bin/textmine.cgi
```

## 機能

- **ワードクラウド**: 単語の出現頻度をフォントサイズで表現
- **共起ネットワーク**: 文単位の共起関係をノード・エッジで表現（ドラッグ移動対応）
- 品詞フィルター（名詞・動詞・形容詞）
- ストップワード設定

## API仕様

**POST** `/cgi-bin/textmine.cgi`

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
