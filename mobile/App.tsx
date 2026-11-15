import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, BackHandler, Dimensions, Pressable, StatusBar as RNStatusBar, StyleSheet, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { WebView } from 'react-native-webview';

// The phone app from the Junction demo, served by the live Money Mentor server.
const APP_URL = 'https://95-216-229-240.sslip.io/app';
const GREEN = '#0fc348';

// The app is drawn edge to edge. The web app pads its header and tab bar with
// the CSS variables --sat / --sab, so hand it the real status and nav bar heights.
function insets() {
  const top = RNStatusBar.currentHeight ?? 24;
  const screen = Dimensions.get('screen').height;
  const win = Dimensions.get('window').height;
  const nav = screen - win - top;
  // Edge to edge, window and screen are the same height, so fall back to the
  // 3-button navigation bar height (48dp); gesture navigation just gets a bit more room.
  const bottom = nav > 8 ? nav : 48;
  return { top: Math.round(top), bottom: Math.round(bottom) };
}

function insetScript() {
  const { top, bottom } = insets();
  return `(function(){
    var s = document.documentElement.style;
    s.setProperty('--sat', '${top}px');
    s.setProperty('--sab', '${bottom}px');
  })(); true;`;
}

export default function App() {
  const web = useRef<any>(null);
  const canGoBack = useRef(false);
  const [failed, setFailed] = useState(false);
  const [key, setKey] = useState(0);
  const { top, bottom } = insets();

  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (canGoBack.current) {
        web.current?.goBack();
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, []);

  const Web = WebView as any;

  return (
    <View style={styles.root}>
      <StatusBar style="dark" translucent />
      {failed ? (
        <View style={[styles.center, { paddingTop: top, paddingBottom: bottom }]}>
          <Text style={styles.title}>No connection</Text>
          <Text style={styles.body}>Money Mentor needs the internet. Check Wi-Fi and try again.</Text>
          <Pressable
            style={styles.button}
            onPress={() => {
              setFailed(false);
              setKey((k) => k + 1);
            }}
          >
            <Text style={styles.buttonText}>Try again</Text>
          </Pressable>
        </View>
      ) : (
        <Web
          key={key}
          ref={web}
          source={{ uri: APP_URL }}
          style={styles.root}
          originWhitelist={['*']}
          javaScriptEnabled
          domStorageEnabled
          mediaPlaybackRequiresUserAction={false}
          allowsInlineMediaPlayback
          setSupportMultipleWindows={false}
          overScrollMode="never"
          bounces={false}
          pullToRefreshEnabled={false}
          textZoom={100}
          injectedJavaScriptBeforeContentLoaded={insetScript()}
          injectedJavaScript={insetScript()}
          startInLoadingState
          renderLoading={() => (
            <View style={[StyleSheet.absoluteFill, styles.splash]}>
              <ActivityIndicator color="#ffffff" size="large" />
            </View>
          )}
          onNavigationStateChange={(s: { canGoBack: boolean }) => {
            canGoBack.current = s.canGoBack;
          }}
          onError={() => setFailed(true)}
          onHttpError={(e: { nativeEvent: { statusCode: number } }) => {
            if (e.nativeEvent.statusCode >= 500) setFailed(true);
          }}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#ffffff' },
  splash: { backgroundColor: GREEN, alignItems: 'center', justifyContent: 'center' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 12 },
  title: { fontSize: 22, fontWeight: '700', color: '#004628' },
  body: { fontSize: 16, color: '#333', textAlign: 'center' },
  button: { marginTop: 8, backgroundColor: '#0a8942', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 24 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
