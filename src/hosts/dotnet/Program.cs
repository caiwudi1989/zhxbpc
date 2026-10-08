using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;

sealed class PluginContext : AssemblyLoadContext
{
    private readonly AssemblyDependencyResolver resolver;
    public PluginContext(string path) : base(isCollectible: true) { resolver = new(path); }
    protected override Assembly? Load(AssemblyName name)
    {
        string? path = resolver.ResolveAssemblyToPath(name);
        return path is null ? null : LoadFromAssemblyPath(path);
    }
    protected override IntPtr LoadUnmanagedDll(string name)
    {
        string? path = resolver.ResolveUnmanagedDllToPath(name);
        return path is null ? IntPtr.Zero : LoadUnmanagedDllFromPath(path);
    }
}

static class Program
{
    public static int Main()
    {
        PluginContext? context = null;
        MethodInfo? call = null;
        string? line;
        while ((line = Console.ReadLine()) != null)
        {
            string? id = null;
            try
            {
                if (line.Length > 65536) throw new ArgumentException("request exceeds host limit");
                using JsonDocument document = JsonDocument.Parse(line);
                JsonElement request = document.RootElement;
                id = request.GetProperty("id").GetString();
                string command = request.GetProperty("command").GetString()!;
                object result;
                if (command == "load")
                {
                    string root = Path.GetFullPath(request.GetProperty("directory").GetString()!);
                    string path = Path.GetFullPath(Path.Combine(root, request.GetProperty("manifest").GetProperty("entry").GetString()!));
                    if (!path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new ArgumentException("entry escapes plugin root");
                    context = new PluginContext(path);
                    Assembly assembly = context.LoadFromAssemblyPath(path);
                    call = assembly.GetTypes().Select(t => t.GetMethod("Call", BindingFlags.Public | BindingFlags.Static)).FirstOrDefault(m => m?.ReturnType == typeof(string));
                    if (call is null) throw new ArgumentException("public static string Call(string) required");
                    result = new { plugin = assembly.GetName().Name, pid = Environment.ProcessId, loader = "AssemblyLoadContext" };
                }
                else if (command == "call")
                {
                    TextWriter output = Console.Out;
                    try
                    {
                        Console.SetOut(Console.Error);
                        string response = (string)call!.Invoke(null, new object[] { line })!;
                        if (response.Length > 65536) throw new ArgumentException("response exceeds host limit");
                        result = JsonSerializer.Deserialize<JsonElement>(response);
                    }
                    finally { Console.SetOut(output); }
                }
                else if (command == "shutdown")
                {
                    call = null;
                    context?.Unload();
                    context = null;
                    result = new { status = "closed" };
                }
                else throw new ArgumentException("unknown host command");
                Console.WriteLine(JsonSerializer.Serialize(new { id, ok = true, result }));
                if (command == "shutdown") return 0;
            }
            catch (Exception error) { Console.WriteLine(JsonSerializer.Serialize(new { id, ok = false, error = error.GetBaseException().Message })); }
        }
        return 0;
    }
}
