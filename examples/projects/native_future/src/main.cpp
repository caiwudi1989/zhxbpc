#include <future>
#include <iostream>
int main(){auto f=std::async(std::launch::async,[]{return 42;});std::cout<<f.get()<<"\n";}
