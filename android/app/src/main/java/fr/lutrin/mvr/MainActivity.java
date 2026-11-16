package fr.lutrin.mvr;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import java.io.OutputStream;

public class MainActivity extends Activity {
    private static final String APP_URL = "https://mvr-app.pages.dev/";
    private WebView web;
    private ValueCallback<Uri[]> filePathCallback;
    private static final int REQ_FILE = 42;

    private static final String JS_HOOK =
        "(function(){if(window.__mvrHook)return;window.__mvrHook=1;"
      + "var orig=HTMLAnchorElement.prototype.click;"
      + "function send(a){var h=a.href||'';var n=a.download||'fichier';"
      + "if(h.indexOf('blob:')===0){fetch(h).then(function(r){return r.blob()}).then(function(b){var f=new FileReader();"
      + "f.onload=function(){AndroidBridge.save(n,b.type||'application/octet-stream',String(f.result).split(',')[1]||'')};f.readAsDataURL(b)});return true}"
      + "if(h.indexOf('data:')===0){var i=h.indexOf(',');var m=h.substring(5,i).split(';')[0]||'application/octet-stream';"
      + "var d=h.substring(i+1);if(h.substring(0,i).indexOf('base64')<0){d=btoa(unescape(d))}AndroidBridge.save(n,m,d);return true}return false}"
      + "HTMLAnchorElement.prototype.click=function(){if(this.hasAttribute('download')&&send(this))return;return orig.call(this)};"
      + "document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[download]');if(a&&send(a)){e.preventDefault()}},true);"
      + "})();";

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        web = new WebView(this);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        web.addJavascriptInterface(new Bridge(), "AndroidBridge");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                String h = u.getHost() == null ? "" : u.getHost();
                if (h.endsWith("pages.dev") || h.endsWith("jsdelivr.net") || h.endsWith("workers.dev")) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception e) {}
                return true;
            }
            @Override public void onPageFinished(WebView v, String url) { v.evaluateJavascript(JS_HOOK, null); }
            @Override public void onPageCommitVisible(WebView v, String url) { v.evaluateJavascript(JS_HOOK, null); }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try { startActivityForResult(Intent.createChooser(i, "Choisir un fichier"), REQ_FILE); }
                catch (Exception e) { filePathCallback = null; return false; }
                return true;
            }
            @Override public void onPermissionRequest(PermissionRequest r) { r.grant(r.getResources()); }
        });
        if (b != null) web.restoreState(b); else web.loadUrl(APP_URL);
        hideBars();
    }

    class Bridge {
        @JavascriptInterface
        public void save(String name, String mime, String b64) {
            try {
                byte[] data = Base64.decode(b64, Base64.DEFAULT);
                ContentValues cv = new ContentValues();
                cv.put(MediaStore.Downloads.DISPLAY_NAME, name);
                cv.put(MediaStore.Downloads.MIME_TYPE, mime);
                cv.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                OutputStream o = getContentResolver().openOutputStream(uri);
                o.write(data); o.close();
                toast("Enregistré dans Téléchargements : " + name);
            } catch (Exception e) { toast("Échec de l'enregistrement : " + e.getMessage()); }
        }
    }

    private void toast(final String m) {
        runOnUiThread(new Runnable() { public void run() { Toast.makeText(MainActivity.this, m, Toast.LENGTH_LONG).show(); } });
    }

    @Override protected void onActivityResult(int req, int res, Intent data) {
        if (req == REQ_FILE && filePathCallback != null) {
            Uri[] out = null;
            if (res == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int n = data.getClipData().getItemCount(); out = new Uri[n];
                    for (int i = 0; i < n; i++) out[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) out = new Uri[]{data.getData()};
            }
            filePathCallback.onReceiveValue(out); filePathCallback = null;
        } else super.onActivityResult(req, res, data);
    }

    private void hideBars() {
        Window w = getWindow();
        w.getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
          | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }
    @Override public void onWindowFocusChanged(boolean f) { super.onWindowFocusChanged(f); if (f) hideBars(); }
    @Override protected void onSaveInstanceState(Bundle b) { super.onSaveInstanceState(b); web.saveState(b); }
    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else moveTaskToBack(true); }
    @Override protected void onPause() { super.onPause(); web.onPause(); }
    @Override protected void onResume() { super.onResume(); web.onResume(); }
}
