package pcide.android;

import dalvik.system.DexClassLoader;
import java.io.File;
import java.net.InetSocketAddress;
import java.lang.reflect.Method;
import org.java_websocket.WebSocket;
import org.java_websocket.handshake.ClientHandshake;
import org.java_websocket.server.WebSocketServer;
import org.json.JSONObject;

public final class RemoteHost extends WebSocketServer {
    private final File root;
    public RemoteHost(int port, File root) {
        super(new InetSocketAddress("127.0.0.1", port), 1);
        this.root = root;
        setConnectionLostTimeout(0);
    }
    public void onOpen(WebSocket client, ClientHandshake handshake) {}
    public void onClose(WebSocket client, int code, String reason, boolean remote) {}
    public void onError(WebSocket client, Exception error) { error.printStackTrace(); }
    public void onStart() { System.out.println("PCIDE Android ART host ready"); }
    public void onMessage(WebSocket client, String text) {
        JSONObject response = new JSONObject();
        try {
            if (text.length() > 65536) throw new IllegalArgumentException("request too large");
            JSONObject request = new JSONObject(text);
            if (!"pcide-dex-v1".equals(request.getString("protocol"))) throw new IllegalArgumentException("unsupported protocol");
            response.put("id", request.getString("id"));
            response.put("runtime", "android-art");
            String method = request.getString("method");
            if (method.equals("host.describe")) {
                response.put("result", new JSONObject().put("loader", "DexClassLoader").put("root", root.toString()));
            } else if (method.equals("dex.call")) {
                JSONObject params = request.getJSONObject("params");
                File dex = new File(root, params.getString("dex")).getCanonicalFile();
                if (!dex.getPath().startsWith(root.getCanonicalPath() + File.separator)) throw new IllegalArgumentException("DEX outside root");
                if (!dex.isFile()) throw new IllegalArgumentException("DEX missing");
                dex.setReadOnly();
                File cache = new File(root, "optimized"); cache.mkdirs();
                DexClassLoader loader = new DexClassLoader(dex.getPath(), cache.getPath(), null, getClass().getClassLoader());
                Class<?> type = loader.loadClass(params.getString("class"));
                Method call = type.getMethod("call", String.class);
                Object result = call.invoke(null, params.optString("argument", "{}"));
                response.put("result", String.valueOf(result));
            } else throw new IllegalArgumentException("unsupported method");
            response.put("ok", true);
        } catch (Throwable error) {
            try { response.put("runtime", "android-art"); response.put("ok", false); response.put("error", error.toString()); }
            catch (Exception ignored) { System.err.println(error); }
        }
        client.send(response.toString());
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("port and DEX root required");
        File root = new File(args[1]).getCanonicalFile(); root.mkdirs();
        new RemoteHost(Integer.parseInt(args[0]), root).start();
    }
}
