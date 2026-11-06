#include <bits/stdc++.h>
using namespace std;
#define pii pair<int, int>

int32_t main() {

  //circumferences, number of layers
  int W=12, L=5;

  //we are assuming the height of each layer to be 1

  //layer at each column needs its own tile configuration

  //if the L is odd, we need another set of tile configuration
  //...to enable growing forward without tweaking to either way

  int H=(L%2==1) ? L*2 : L;

  vector<int> color(H, 0);
  for(int i=0; i<H; ++i) color[i]=i%L;

  //the binding opponent
  //0-1
  //-x-
  //2-3
  vector<vector<int>> binding(W*H, 4);

  auto mapping=[&](int i, int j) {
    return i*W+j;
  };

  for(int i=0; i<H; ++i) for(int j=0; j<W; ++j) for(int k=0; k<4; ++k) {

    int ni=(k<=1) ? (i+1)%H : (i+H-1)%H;
    int nj=(k%2==0) ? j : (j+1)%W;

    binding[mapping(i, j)][k]=mapping(ni, nj);
  }

  //incorrect seed config: they have to be at least 2-layered forming a "w"-like shape
  int SEEDH=10; //for the stability
  int SIDX=H*W;
  unordered_map<vector<int>> seed(SEEDH*W, 4);
  for(int i=0; i<SEEDH; ++i) for(int j=0; j<W; ++j) for(int k=0; k<4; ++k) {

    int u=i+SIDX, m=mapping(u, j);
    if(seed[m].find()==seed.end()) seed[m]=vector<int>(4);

    if(i==0 && k>=2) {
      seed[m][k]=-1;
      continue;
    }

    //the final seed binds to one of the row of general seeds
    int ni=(k<=1) ? (i+1==SEEDH ? 0 : u+1) : u-1;
    int nj=(k%2==0) ? j : (j+1)%W;

    seed[m][k]=mapping(ni, nj);
  }

  unordered_map<pii> 


  return 0;
}