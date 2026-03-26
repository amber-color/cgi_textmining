# 日本語テキストマイニング

Pythonのデスクトップ GUIアプリです。
テキストを入力またはファイルから読み込み、形態素解析してワードクラウド・共起ネットワークをブラウザで表示します。

## 起動方法

```
python app.py
```

## ディレクトリ構成

```
app.py                      # メインアプリ（tkinter GUI）
static/
  d3.min.js                 # D3.js v7（要配置）
  d3.layout.cloud.min.js    # d3-cloud（要配置）
lib/
  janome/                   # janomeをwhlから解凍して配置
```

## セットアップ

### 1. janome の配置

```bash
pip install janome --target=lib/
```

または pip download でwhlを取得して解凍して `lib/` に配置。

### 2. D3.js の配置

- D3.js v7 の `d3.min.js` を `static/` に配置
- d3-cloud の `d3.layout.cloud.min.js` を `static/` に配置

## 機能

| 機能 | 説明 |
|------|------|
| テキスト直接入力 | テキストエリアに日本語テキストを貼り付け |
| TXTファイル読み込み | ローカルの .txt ファイルを開く |
| CSVファイル読み込み | ローカルの .csv ファイルを開く（UTF-8/Shift-JIS対応） |
| ワードクラウド | 単語の出現頻度をフォントサイズで表現 |
| 共起ネットワーク | 文単位の共起関係をノード・エッジで表現 |
| 品詞フィルター | 名詞・動詞・形容詞を選択可能 |
| ストップワード | カンマ区切りで除外語を指定 |

分析結果はブラウザで自動的に表示されます（D3.js による描画）。
