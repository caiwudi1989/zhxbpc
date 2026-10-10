#include <thread>
#include <mutex>
#include <iostream>
int main(){int n=0;std::mutex m;auto work=[&]{for(int i=0;i<100;++i){std::lock_guard<std::mutex> lock(m);++n;}};std::thread a(work),b(work);a.join();b.join();std::cout<<n<<"\n";}
