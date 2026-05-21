import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  Modal,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from 'react-native';
import { StatusBar } from 'expo-status-bar';

declare const process: { env: Record<string, string | undefined> };

type User = { username: string; role: 'admin' | 'user'; must_change_pw?: boolean };

type Checkin = {
  date: string;
  nb: number;
  sb: number;
  sh: number;
  co: number;
  wi: number;
  jo: number;
};

type ScoreRow = {
  rank: number;
  username: string;
  score: number;
  days: number;
  avg: number;
  last_date: string;
};

type LeagueKey = 'champions' | 'europa' | 'conference' | 'history' | 'stats';

const API_ROOT = (process.env.EXPO_PUBLIC_API_BASE || 'https://udako.libertronics.org').replace(/\/$/, '');
const API_BASE = `${API_ROOT}/api`;
const WEB_URL = (process.env.EXPO_PUBLIC_WEB_URL || API_ROOT).replace(/\/$/, '');

const MULT = {
  nb: 1.0,
  sb: 1.5,
  sh: 0.75,
  co: 1.25,
  wi: 1.5,
  jo: 1.25
};

async function apiCall(endpoint: string, method: string = 'GET', body: unknown = null) {
  const options: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include'
  };

  if (body) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${endpoint}`, options);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }

  return data;
}

function today() {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  return d.toISOString().slice(0, 10);
}

function fmt(n: number) {
  return Number.isFinite(n) ? n.toFixed(1) : '0.0';
}

function calcScore(c: Checkin) {
  const wine = typeof c.wi === 'number' ? c.wi : 0;
  return c.nb * MULT.nb + c.sb * MULT.sb + c.sh * MULT.sh + c.co * MULT.co + wine * MULT.wi + c.jo * MULT.jo;
}

function buildTotals(checkins: Checkin[]) {
  return checkins.reduce(
    (acc, c) => {
      acc.nb += c.nb;
      acc.sb += c.sb;
      acc.sh += c.sh;
      acc.co += c.co;
      acc.wi += c.wi || 0;
      acc.jo += c.jo;
      return acc;
    },
    { nb: 0, sb: 0, sh: 0, co: 0, wi: 0, jo: 0 }
  );
}

function TabButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.tabButton, active && styles.tabButtonActive]}>
      <Text style={[styles.tabButtonText, active && styles.tabButtonTextActive]}>{label}</Text>
    </Pressable>
  );
}

function Scoreboard({ rows, totalLabel }: { rows: ScoreRow[]; totalLabel: string }) {
  return (
    <View style={styles.scoreboard}>
      <View style={[styles.scoreRow, styles.scoreHeader]}>
        <Text style={styles.scoreHeaderText}>#</Text>
        <Text style={styles.scoreHeaderText}>User</Text>
        <Text style={[styles.scoreHeaderText, styles.scoreRight]}>{totalLabel}</Text>
        <Text style={[styles.scoreHeaderText, styles.scoreRight]}>Days</Text>
        <Text style={[styles.scoreHeaderText, styles.scoreRight]}>Avg</Text>
        <Text style={[styles.scoreHeaderText, styles.scoreRight]}>Last</Text>
      </View>
      {rows.map(row => (
        <View key={`${row.username}-${row.rank}`} style={styles.scoreRow}>
          <Text style={styles.scoreRank}>{row.rank}</Text>
          <Text style={styles.scoreUser}>{row.username}</Text>
          <Text style={[styles.scoreValue, styles.scoreRight]}>{fmt(row.score)}</Text>
          <Text style={[styles.scoreValue, styles.scoreRight]}>{row.days}</Text>
          <Text style={[styles.scoreValue, styles.scoreRight]}>{fmt(row.avg)}</Text>
          <Text style={[styles.scoreValue, styles.scoreRight]}>{row.last_date}</Text>
        </View>
      ))}
    </View>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<LeagueKey>('champions');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [checkins, setCheckins] = useState<Checkin[]>([]);
  const [champions, setChampions] = useState<ScoreRow[]>([]);
  const [europa, setEuropa] = useState<ScoreRow[]>([]);
  const [conference, setConference] = useState<ScoreRow[]>([]);
  const [showCheckin, setShowCheckin] = useState(false);
  const [counts, setCounts] = useState({ nb: 0, sb: 0, sh: 0, co: 0, wi: 0, jo: 0 });

  const totals = useMemo(() => buildTotals(checkins), [checkins]);
  const totalScore = useMemo(() => checkins.reduce((sum: number, c: Checkin) => sum + calcScore(c), 0), [checkins]);
  const avgScore = useMemo(() => (checkins.length ? totalScore / checkins.length : 0), [checkins, totalScore]);
  const bestScore = useMemo(() => checkins.reduce((best: number, c: Checkin) => Math.max(best, calcScore(c)), 0), [checkins]);

  const loadAll = useCallback(async () => {
    const [championsData, europaData, conferenceData, checkinsData] = await Promise.all([
      apiCall('/scoreboard?mode=champions'),
      apiCall('/scoreboard?mode=europa'),
      apiCall('/scoreboard?mode=conference'),
      apiCall('/checkins')
    ]);

    setChampions(championsData.scoreboard || []);
    setEuropa(europaData.scoreboard || []);
    setConference(conferenceData.scoreboard || []);
    setCheckins(checkinsData.checkins || []);
  }, []);

  const bootstrap = useCallback(async () => {
    try {
      const me = await apiCall('/auth/me');
      setUser(me.user);
      await loadAll();
    } catch (err) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [loadAll]);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const handleLogin = async () => {
    setError('');
    try {
      const data = await apiCall('/auth/login', 'POST', {
        username: username.trim().toLowerCase(),
        password
      });
      setUser(data.user);
      await loadAll();
    } catch (err) {
      setError('Invalid username or password.');
    }
  };

  const handleLogout = async () => {
    try {
      await apiCall('/auth/logout', 'POST');
    } catch {
      // ignore
    }
    setUser(null);
    setUsername('');
    setPassword('');
  };

  const adjustCount = (key: keyof typeof counts, delta: number) => {
    setCounts((prev: typeof counts) => ({ ...prev, [key]: Math.max(0, prev[key] + delta) }));
  };

  const openCheckin = () => {
    setCounts({ nb: 0, sb: 0, sh: 0, co: 0, wi: 0, jo: 0 });
    setShowCheckin(true);
  };

  const submitCheckin = async () => {
    await apiCall('/checkins', 'POST', { ...counts, date: today() });
    setShowCheckin(false);
    await loadAll();
  };

  const eqValue =
    counts.nb * MULT.nb +
    counts.sb * MULT.sb +
    counts.sh * MULT.sh +
    counts.co * MULT.co +
    counts.wi * MULT.wi +
    counts.jo * MULT.jo;

  if (loading) {
    return (
      <SafeAreaView style={styles.centered}>
        <ActivityIndicator color="#e8c84a" />
      </SafeAreaView>
    );
  }

  if (!user) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="light" />
        <View style={styles.loginCard}>
          <Text style={styles.loginTitle}>UDAKO CL</Text>
          <Text style={styles.loginSubtitle}>Champions League</Text>
          <TextInput
            value={username}
            onChangeText={setUsername}
            placeholder="Username"
            placeholderTextColor="#666"
            style={styles.input}
            autoCapitalize="none"
          />
          <TextInput
            value={password}
            onChangeText={setPassword}
            placeholder="Password"
            placeholderTextColor="#666"
            style={styles.input}
            secureTextEntry
          />
          {error ? <Text style={styles.errorText}>{error}</Text> : null}
          <Pressable style={styles.primaryButton} onPress={handleLogin}>
            <Text style={styles.primaryButtonText}>Sign in</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <Text style={styles.logo}>UDAKO</Text>
        <View style={styles.headerRight}>
          <Text style={styles.userChip}>Signed in as {user.username}</Text>
          <View style={styles.headerActions}>
            <Pressable onPress={() => Linking.openURL(WEB_URL)}>
              <Text style={styles.linkText}>Open web</Text>
            </Pressable>
            <Pressable onPress={handleLogout}>
              <Text style={styles.linkText}>Sign out</Text>
            </Pressable>
          </View>
        </View>
      </View>

      <View style={styles.tabs}>
        <TabButton label="Champions" active={tab === 'champions'} onPress={() => setTab('champions')} />
        <TabButton label="Europa" active={tab === 'europa'} onPress={() => setTab('europa')} />
        <TabButton label="Conference" active={tab === 'conference'} onPress={() => setTab('conference')} />
        <TabButton label="History" active={tab === 'history'} onPress={() => setTab('history')} />
        <TabButton label="Statistics" active={tab === 'stats'} onPress={() => setTab('stats')} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {tab === 'champions' ? (
          <>
            <View style={styles.summaryRow}>
              <View style={styles.summaryCard}>
                <Text style={styles.summaryLabel}>Total eq</Text>
                <Text style={styles.summaryValue}>{fmt(totalScore)}</Text>
              </View>
              <View style={styles.summaryCard}>
                <Text style={styles.summaryLabel}>Days logged</Text>
                <Text style={styles.summaryValue}>{checkins.length}</Text>
              </View>
              <View style={styles.summaryCard}>
                <Text style={styles.summaryLabel}>Daily avg</Text>
                <Text style={styles.summaryValue}>{fmt(avgScore)}</Text>
              </View>
              <View style={styles.summaryCard}>
                <Text style={styles.summaryLabel}>Best day</Text>
                <Text style={styles.summaryValue}>{fmt(bestScore)}</Text>
              </View>
            </View>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>Champions League</Text>
              <Pressable style={styles.ghostButton} onPress={openCheckin}>
                <Text style={styles.ghostButtonText}>Check in</Text>
              </Pressable>
            </View>
            <Scoreboard rows={champions} totalLabel="Total eq" />
          </>
        ) : null}

        {tab === 'europa' ? (
          <>
            <Text style={styles.sectionTitle}>Europa League</Text>
            <Scoreboard rows={europa} totalLabel="Total eq" />
          </>
        ) : null}

        {tab === 'conference' ? (
          <>
            <Text style={styles.sectionTitle}>Conference League</Text>
            <Scoreboard rows={conference} totalLabel="Total joints" />
          </>
        ) : null}

        {tab === 'history' ? (
          <>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>My History</Text>
              <Pressable style={styles.ghostButton} onPress={openCheckin}>
                <Text style={styles.ghostButtonText}>Check in</Text>
              </Pressable>
            </View>
            {checkins.length === 0 ? (
              <Text style={styles.mutedText}>No check-ins yet.</Text>
            ) : (
              checkins.map((entry: Checkin) => (
                <View key={entry.date} style={styles.historyRow}>
                  <Text style={styles.historyDate}>{entry.date}</Text>
                  <Text style={styles.historyValue}>NB {entry.nb} SB {entry.sb} SH {entry.sh} CO {entry.co} WI {entry.wi || 0} JO {entry.jo}</Text>
                  <Text style={styles.historyValue}>Eq {fmt(calcScore(entry))}</Text>
                </View>
              ))
            )}
          </>
        ) : null}

        {tab === 'stats' ? (
          <>
            <Text style={styles.sectionTitle}>Consumption Overview</Text>
            <View style={styles.statsTable}>
              <View style={styles.statsRow}><Text style={styles.statsLabel}>Normal beer</Text><Text style={styles.statsValue}>{totals.nb}</Text></View>
              <View style={styles.statsRow}><Text style={styles.statsLabel}>Special beer</Text><Text style={styles.statsValue}>{totals.sb}</Text></View>
              <View style={styles.statsRow}><Text style={styles.statsLabel}>Shot</Text><Text style={styles.statsValue}>{totals.sh}</Text></View>
              <View style={styles.statsRow}><Text style={styles.statsLabel}>Cocktail</Text><Text style={styles.statsValue}>{totals.co}</Text></View>
              <View style={styles.statsRow}><Text style={styles.statsLabel}>Wine</Text><Text style={styles.statsValue}>{totals.wi}</Text></View>
              <View style={styles.statsRow}><Text style={styles.statsLabel}>Joint</Text><Text style={styles.statsValue}>{totals.jo}</Text></View>
            </View>
          </>
        ) : null}
      </ScrollView>

      <Modal visible={showCheckin} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.sectionTitle}>Daily Check-in</Text>
            {(['nb', 'sb', 'sh', 'co', 'wi', 'jo'] as const).map(key => (
              <View key={key} style={styles.counterRow}>
                <Text style={styles.counterLabel}>{key.toUpperCase()}</Text>
                <View style={styles.counterControls}>
                  <Pressable style={styles.counterButton} onPress={() => adjustCount(key, -1)}>
                    <Text style={styles.counterButtonText}>-</Text>
                  </Pressable>
                  <Text style={styles.counterValue}>{counts[key]}</Text>
                  <Pressable style={styles.counterButton} onPress={() => adjustCount(key, 1)}>
                    <Text style={styles.counterButtonText}>+</Text>
                  </Pressable>
                </View>
              </View>
            ))}
            <Text style={styles.mutedText}>Eq {eqValue.toFixed(2)}</Text>
            <View style={styles.modalActions}>
              <Pressable style={styles.ghostButton} onPress={() => setShowCheckin(false)}>
                <Text style={styles.ghostButtonText}>Cancel</Text>
              </Pressable>
              <Pressable style={styles.primaryButton} onPress={submitCheckin}>
                <Text style={styles.primaryButtonText}>Save</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f11'
  },
  centered: {
    flex: 1,
    backgroundColor: '#0f0f11',
    alignItems: 'center',
    justifyContent: 'center'
  },
  header: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2828',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  logo: {
    color: '#e8c84a',
    fontSize: 20,
    fontWeight: '700',
    letterSpacing: 2
  },
  headerRight: {
    alignItems: 'flex-end'
  },
  headerActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 4
  },
  userChip: {
    color: '#ccc',
    fontSize: 12
  },
  linkText: {
    color: '#e8c84a',
    fontSize: 12,
    marginTop: 4
  },
  tabs: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2828'
  },
  tabButton: {
    paddingVertical: 10,
    paddingHorizontal: 12
  },
  tabButtonActive: {
    borderBottomWidth: 2,
    borderBottomColor: '#e8c84a'
  },
  tabButtonText: {
    color: '#666',
    fontSize: 12
  },
  tabButtonTextActive: {
    color: '#e8c84a'
  },
  content: {
    padding: 16
  },
  summaryRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 12
  },
  summaryCard: {
    backgroundColor: '#18171a',
    borderWidth: 1,
    borderColor: '#2a2828',
    borderRadius: 10,
    padding: 12,
    minWidth: 140
  },
  summaryLabel: {
    color: '#666',
    fontSize: 11,
    textTransform: 'uppercase'
  },
  summaryValue: {
    color: '#e8c84a',
    fontSize: 18,
    fontWeight: '600',
    marginTop: 4
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8
  },
  sectionTitle: {
    color: '#e8c84a',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8
  },
  scoreboard: {
    gap: 8
  },
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: '#2a2828',
    borderRadius: 10,
    backgroundColor: '#18171a'
  },
  scoreHeader: {
    backgroundColor: 'transparent',
    borderColor: 'transparent',
    paddingBottom: 4
  },
  scoreHeaderText: {
    color: '#666',
    fontSize: 11,
    textTransform: 'uppercase',
    flex: 1
  },
  scoreRank: {
    color: '#e8c84a',
    width: 24
  },
  scoreUser: {
    color: '#e8e4dc',
    flex: 1
  },
  scoreValue: {
    color: '#ccc',
    flex: 1
  },
  scoreRight: {
    textAlign: 'right'
  },
  ghostButton: {
    borderWidth: 1,
    borderColor: '#444',
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 12
  },
  ghostButtonText: {
    color: '#ccc',
    fontSize: 12
  },
  historyRow: {
    borderWidth: 1,
    borderColor: '#2a2828',
    borderRadius: 10,
    padding: 10,
    marginBottom: 8,
    backgroundColor: '#18171a'
  },
  historyDate: {
    color: '#e8c84a',
    marginBottom: 4
  },
  historyValue: {
    color: '#ccc',
    fontSize: 12
  },
  statsTable: {
    borderWidth: 1,
    borderColor: '#2a2828',
    borderRadius: 10,
    backgroundColor: '#18171a'
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1e1d20'
  },
  statsLabel: {
    color: '#ccc'
  },
  statsValue: {
    color: '#e8c84a',
    fontWeight: '600'
  },
  loginCard: {
    margin: 24,
    padding: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#2a2828',
    backgroundColor: '#18171a'
  },
  loginTitle: {
    color: '#e8c84a',
    fontSize: 28,
    fontWeight: '700',
    textAlign: 'center'
  },
  loginSubtitle: {
    color: '#666',
    textAlign: 'center',
    marginBottom: 16
  },
  input: {
    borderWidth: 1,
    borderColor: '#333',
    borderRadius: 8,
    padding: 12,
    color: '#e8e4dc',
    marginBottom: 12
  },
  primaryButton: {
    backgroundColor: '#e8c84a',
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center'
  },
  primaryButtonText: {
    color: '#0f0f11',
    fontWeight: '600'
  },
  errorText: {
    color: '#e87a7a',
    textAlign: 'center',
    marginBottom: 8
  },
  mutedText: {
    color: '#666'
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    alignItems: 'center',
    justifyContent: 'center'
  },
  modalCard: {
    width: '90%',
    backgroundColor: '#18171a',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#333',
    padding: 16
  },
  counterRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10
  },
  counterLabel: {
    color: '#ccc',
    width: 40
  },
  counterControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8
  },
  counterButton: {
    width: 32,
    height: 32,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#444',
    alignItems: 'center',
    justifyContent: 'center'
  },
  counterButtonText: {
    color: '#ccc',
    fontSize: 16
  },
  counterValue: {
    color: '#e8c84a',
    minWidth: 24,
    textAlign: 'center'
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 12
  }
});
