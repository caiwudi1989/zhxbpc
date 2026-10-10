#include <algorithm>
#include <iostream>
#include <vector>
int main(){std::vector<int> v{3,1,2};std::sort(v.begin(),v.end());for(auto n:v)std::cout<<n;std::cout<<"\n";}
