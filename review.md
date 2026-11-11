# Protocol 3 / nanotube aTAM review

更新日: 2026-11-11  
対象: `rgrow/tile-config-sample.cpp` と `rgrow/protocol3.py`

## 到達した状態

- 円周は `W = 6`、Seed は軸方向 2 層なので `SEEDH * W = 12` タイルである。
- `j` はチューブの周期方向、`i` は開いた軸方向として扱う。
- Seed の 12 タイルは、重複なしで `tube-diagonals` canvas 上の 12 セルへ配置される。
- C++ の Seed 内部の各隣接辺は、Python 側で対応する rGrow の N/E/W/S 移動先と一致することを検査する。
- aTAM は `tau = 2`、各有効 glue の強度は `1`。したがって、通常は強度 1 の一致が二つ必要である。
- rGrow 用の tileset、CSV 出力、canvas PNG 描画、タイル ID 表示、タイルごとの透明度差を備える。

座標系回転の**直前**のチェックポイントは Git commit `730ffc6` (`Checkpoint before coordinate rotation`)。この review で説明する最終座標系の実装は、その後の未コミット変更にある。

## 最終設計の基準

### 方向の番号と順序

設計表（C++ / Python の論理表）の方向番号は固定である。

| 番号 | 方向 |
| ---: | :--- |
| 0 | N |
| 1 | E |
| 2 | W |
| 3 | S |

一方 rGrow の tile edge 配列は `N, E, S, W` の順である。そのため Python 側では論理表を `N, E, W, S` のまま保持し、rGrow へ渡す直前に順序を変換する。ここを同じ順序だと仮定すると、W と S が入れ替わり、正しい glue を持っていても別方向に成長する。

### 論理隣接表

通常タイルでは、`j` が周期方向、`i` が軸方向になるよう、各辺の接続先を次で作る。

```cpp
ni = i + (k % 2) - (j % 2);
nj = j + ((k <= 1) ? 1 : -1);
```

`regular_id(ni, nj)` はタイル**型**のインデックスなので、`H` と `W` で周期化する。一方、実際に伸びる canvas 座標まで周期化してはいけない。型の周期と物理座標の開放方向は別物である。

Seed も同じ局所規則を使い、`i` 方向だけを有限にする。

```cpp
if (ni < 0)          target = NO_TILE;
else if (ni >= SEEDH) target = regular_id(0, nj);
else                 target = seed_id(ni, nj);
```

これにより、Seed は「`i` が 0, 1 の二層」かつ「各層に `j = 0..5` の六位置」という明確な 12 タイル構造になる。`SEEDH * W` から導かれるため、24 や 12 を別途ハードコードしない。

### Seed の物理座標

Seed をグラフ探索の到着順で置くのではなく、論理座標 `(i, j)` から直接配置する。原点を `(origin_y, origin_x)` とすると、`tube-diagonals` の raw canvas 座標は次で得る。

```text
unwrapped_y = origin_y - j
y           = unwrapped_y mod circumference
north_seams = -floor(unwrapped_y / circumference)
x           = origin_x + i + floor(j / 2)
              - north_seams * (circumference / 2)
```

最後の補正は、rGrow が北端から南端へ wrap するときの列シフトである。この式は単なる表示用の変換ではない。隣接表の N/E/W/S と rGrow の `CanvasTubeDiagonals` の移動規則が同じセルを指すための埋め込みである。

## 試行錯誤と学び

| テーマ | 起きたこと | 原因 | 最終的な扱い・今後の基準 |
| :--- | :--- | :--- | :--- |
| canvas 名 | `TubeDiagonals` が `Unknown canvas type` になった。 | rGrow の enum 名は表示用の CamelCase ではない。 | `canvas_type="tube-diagonals"` を使う。rGrow の受け付ける文字列はエラー文と公式 API の表記を優先する。 |
| 円周の変更 | 円周を 12 から 6 に変更後も、Seed 個数・配置の前提が残り、重なりや不整合が出た。 | `W` の変更を、派生量の変更へ連鎖させていなかった。 | `W = CIRCUMFERENCE`、`SEEDH = SEED_LAYER_COUNT`、Seed 数は常に `SEEDH * W` として導く。 |
| Seed ID | Seed ID が通常タイルの後ろに連続せず、意図しない大きな番号になり得た。 | `mapping(SIDX + i, j)` は `SIDX` まで `W` 倍してしまう。 | `seed_id(i, j) = SIDX + i * W + j` を独立した関数として使う。Seed を `regular_id` に通さない。 |
| Seed の C++ 容器 | `unordered_map<vector<int>>` と `find()` の使い方が成立しなかった。 | 「各 Seed に 4 辺」が固定長であるのに、連想コンテナとして扱っていた。 | `vector<array<int, 4>>` を使う。固定構造は固定長配列で表す。 |
| 方向の解釈 | N/E/W/S の対応を一度誤り、意図した辺とは異なる接続になった。 | 設計表の順序と rGrow の edge 順序を混同した。 | 上の二つの順序を分離して保持し、rGrow 変換箇所だけで並べ替える。 |
| glue の対 | A の E と B の W を結合したいのに、同一方向へ名前を置く誤解があった。 | glue はタイルの方向ではなく、向かい合う二辺の一致で働く。 | `A.E` と `B.W` に同じ glue 名・強度を与える。論理表の `A.direction -> B` からは `B.opposite(direction)` と同じ glue component にする。 |
| `tau = 2` | 正しい tile 型でも前縁が縮む／単独では出現しないように見えた。 | 強度 1 glue 一つでは閾値 2 を越えられない。 | `tau=2` と強度 1 は協調結合を意味する。狙った位置に強度 1 の一致辺が二つ同時に存在するかを、glue 名だけでなく物理隣接セルでも確認する。 |
| wrap の意味 | 「接続先 ID を modulo にしているので wrap 済み」と解釈しがちだった。 | 型番号の modulo は互換性の周期であり、canvas 上のセル隣接を作らない。 | 型の wrap と physical tube wrap を別に検証する。後者は `tube-diagonals` の座標遷移と Seed 配置で保証する。 |
| BFS Seed 配置 | 最初に到達した座標を採用する BFS で、Seed が歪み、重複や不連続な front を生んだ。 | C++ の表は単なる探索木ではなく、複数経路で拘束された幾何グラフである。到着順は幾何を決めない。 | Seed の既知の論理座標 `(i,j)` から直接配置する。各内部 edge について `move(source, direction) == target_coordinate` を assertion で確認する。 |
| out-of-bounds / unsigned | `Point (5, 0) is out of bounds`、負値を unsigned へ変換する失敗が出た。 | rGrow Seed 座標は canvas 範囲内の非負整数でなければならず、tube-diagonals には列ガードもある。 | `y` を円周で正規化し、最小 `x` を `first_usable_x` へ平行移動してから TileSet に渡す。 |
| i/j の役割 | 伸長方向が意図と違い、`j` と `i` を画面座標と同一視すると説明も実装も崩れた。 | `(i,j)` はタイル設計の論理座標で、PNG の `(y,x)` ではない。 | 最終設計では `j=円周`、`i=軸`。この役割変更は Python の表示座標だけでなく、C++ と Python の隣接表、Seed 境界、埋め込み式を一緒に回転する。 |
| 可視化 | 同じ色のタイルが続くと、どの型がどこに置かれたか診断しにくかった。 | phase 色だけでは個別タイル型を区別できない。 | base 色に tile ごとの alpha 差を与え、必要に応じて `--tile-labels` で tile ID を重ねる。描画は rGrow の `row + column, column` 変換に合わせる。 |

## 今後の変更手順

1. まず C++ の論理隣接表を変更し、Python の `build_tiles()` に同じ式を写す。
2. 方向順序が `N,E,W,S` の論理表であることを確認し、rGrow 変換だけが `N,E,S,W` であることを確認する。
3. `CIRCUMFERENCE` を変えたら、Seed 数を数値で書き換えず `SEEDH * W`、ID 範囲を `H * W` から導く。
4. Seed の各内部辺について、論理 target と canvas の移動先が一致することを検査する。セル重複も同時に検査する。
5. `tau` または glue strength を変えたら、各成長位置で合計強度が閾値以上かを確認する。`tau=2, strength=1` なら通常は二辺必要である。
6. その後にだけ rGrow を実行し、CSV の `seed_coordinate` / `frontier`、`--tile-labels` 付き PNG を確認する。
7. 寸法・座標系・方向順序に触れる変更の直前には Git checkpoint を作る。

## 実行時の最小コマンド例

```powershell
python .\rgrow\protocol3.py `
  --output .\rgrow\results\p3-config.csv `
  --simulate --events 2000 `
  --plot .\rgrow\results\p3-vis.png `
  --tile-labels
```

`--simulate` を付けない場合は、tileset を実行せず設計 CSV のみ出力する。結果を比較するときは、先に CSV の Seed 座標と frontier を確認してから PNG を読むと、論理・物理・描画のどの層に問題があるかを切り分けやすい。
