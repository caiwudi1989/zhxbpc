using System;
using System.Threading;
using System.Threading.Tasks;
using var token=new CancellationTokenSource();
token.Cancel();
try { await Task.Delay(1000,token.Token); } catch(OperationCanceledException) { Console.WriteLine("cancelled"); }
