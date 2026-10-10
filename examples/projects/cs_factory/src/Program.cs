using System;
var factory = new Func<int>(() => 42);
Console.WriteLine(factory());
