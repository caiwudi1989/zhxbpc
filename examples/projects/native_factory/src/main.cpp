#include <memory>
#include <iostream>
struct Product{virtual ~Product()=default;virtual int value()const=0;};
struct Tool:Product{int value()const override{return 42;}};
std::unique_ptr<Product> create(){return std::make_unique<Tool>();}
int main(){std::cout<<create()->value()<<"\n";}
