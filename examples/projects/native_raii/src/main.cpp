#include <memory>
#include <iostream>
int main(){auto p=std::make_unique<int>(42);std::cout<<*p<<"\n";}
