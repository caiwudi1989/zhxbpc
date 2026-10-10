#include <fstream>
#include <iostream>
int main(){{std::ofstream out("data.txt");out<<"hello";}std::ifstream in("data.txt");std::string text;in>>text;std::cout<<text<<"\n";}
