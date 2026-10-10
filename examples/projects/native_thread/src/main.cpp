#include <thread>
#include <iostream>
int main(){int result=0;std::thread t([&]{result=42;});t.join();std::cout<<result<<"\n";}
