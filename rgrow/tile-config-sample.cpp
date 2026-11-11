#include <array>
#include <vector>

using namespace std;

int main() {
  // Named model parameters.  W follows the requested tube circumference;
  // the Seed has two structural layers, so it has 2 * W Seed tiles.
  const int CIRCUMFERENCE = 6;
  const int LAYER_COUNT = 5;
  const int SEED_LAYER_COUNT = 2;
  const int W = CIRCUMFERENCE;
  const int L = LAYER_COUNT;
  const int H = (L % 2 == 1) ? L * 2 : L;
  const int SEEDH = SEED_LAYER_COUNT;
  const int NO_TILE = -1;

  // The regular tile IDs occupy [0, H * W).  ``binding`` stores the
  // direction-specific logical opponent ID: N, E, W, S.
  const auto regular_id = [W, H](int i, int j) {
    return ((i % H + H) % H) * W + ((j % W + W) % W);
  };
  vector<array<int, 4>> binding(H * W);

  for (int i = 0; i < H; ++i) {
    for (int j = 0; j < W; ++j) {
      for (int k = 0; k < 4; ++k) {
        const int ni = (k <= 1) ? (i + 1) % H : (i + H - 1) % H;
        const int nj = j + (k % 2) - (i % 2);
        binding[regular_id(i, j)][k] = regular_id(ni, nj);
      }
    }
  }

  // Seed IDs follow the regular IDs contiguously:
  // [H * W, H * W + SEEDH * W).  Do not pass a seed row through
  // regular_id/mapping: it would multiply the H * W offset by W.
  const int SIDX = H * W;
  const auto seed_id = [SIDX, W](int depth, int position) {
    return SIDX + depth * W + ((position % W + W) % W);
  };
  vector<array<int, 4>> seed(SEEDH * W);

  for (int i = 0; i < SEEDH; ++i) {
    for (int j = 0; j < W; ++j) {
      const int m = seed_id(i, j);
      const int local_seed_index = m - SIDX;
      for (int k = 0; k < 4; ++k) {
        if (i == 0 && k >= 2) {
          seed[local_seed_index][k] = NO_TILE;
          continue;
        }

        const int nj = j + (k % 2) - (i % 2);
        if (k <= 1 && i + 1 == SEEDH) {
          // The final seed row targets regular phase zero.
          seed[local_seed_index][k] = regular_id(0, nj);
        } else if (k <= 1) {
          seed[local_seed_index][k] = seed_id(i + 1, nj);
        } else {
          seed[local_seed_index][k] = seed_id(i - 1, nj);
        }
      }
    }
  }

  return 0;
}
