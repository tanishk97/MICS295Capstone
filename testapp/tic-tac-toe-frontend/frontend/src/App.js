import { useMemo, useState } from 'react';
import './App.css';

const LINES = [
  [0,1,2],[3,4,5],[6,7,8],
  [0,3,6],[1,4,7],[2,5,8],
  [0,4,8],[2,4,6]
];

const empty = () => Array(9).fill(' ');
const toStr = (a) => a.join('');
const toArr = (s) => s.split('');

function winner(b){
  for (const [a,b2,c] of LINES){
    if (b[a] !== ' ' && b[a] === b[b2] && b[a] === b[c]) return b[a];
  }
  return null;
}
const full = (b) => b.every(x => x !== ' ');

export default function App(){
  const [board, setBoard] = useState(empty());
  const [yourMark] = useState('x');      // you are 'x'
  const [thinking, setThinking] = useState(false);
  const [err, setErr] = useState('');

  const status = useMemo(() => {
    const w = winner(board);
    if (w) return (w === yourMark ? 'You win! 🏆' : 'Computer wins 🤖');
    const fullBoard = full(board);
    if (fullBoard) return 'Draw.';
    return thinking ? 'Computer is thinking…' : 'Your move';
  }, [board, thinking, yourMark]);
  

  const reset = () => { setBoard(empty()); setErr(''); setThinking(false); };

  async function play(i){
    // stop if we shouldn't act
    const fullBoard = full(board);
    if (thinking || board[i] !== ' ' || winner(board) || fullBoard) return;
  
    // 1) apply your move locally
    const next = board.slice();
    next[i] = yourMark;           // 'x'
    setBoard(next);
  
    // if your move already ends the game, stop
    if (winner(next) || (typeof full === 'function' ? full(next) : full(next))) return;
  
    try {
      // 2) show spinner
      setThinking(true);
      setErr('');
  
      // 3) build the 9-char board string
      const boardStr = next.join('');
  
      // 4) encode spaces as '+' (your server expects '+', not %20)
      const qs = encodeURIComponent(boardStr).replace(/%20/g, '+');
  
      // 5) call backend via CRA proxy (/api → 127.0.0.1:5000)
      const res = await fetch(`/api?board=${qs}`);
      if (!res.ok) throw new Error(`Backend ${res.status}`);
  
      // 6) read reply and DO NOT trim trailing spaces
      const raw = await res.text();
      const boardFromServer = normalizeBoardString(raw);
  
      if (boardFromServer.length !== 9) {
        // helpful debug if something goes wrong
        console.error('RAW:', JSON.stringify(raw));
        console.error('NORM:', JSON.stringify(boardFromServer), 'len=', boardFromServer.length);
        throw new Error(`Bad response: got ${boardFromServer.length} chars`);
      }
  
      // 7) apply computer's move
      setBoard(boardFromServer.split(''));
    } catch (e) {
      setErr(e.message || 'Request failed');
    } finally {
      // 8) ALWAYS turn it off
      setThinking(false);
    }
  }
  

  function normalizeBoardString(raw) {
    let t = String(raw);
  
    // remove only newlines (keep spaces!)
    t = t.replace(/\r?\n/g, '');
  
    // if server wrapped in quotes, unwrap (preserve inside spaces)
    if (t.startsWith('"') && t.endsWith('"')) {
      t = t.slice(1, -1);
    }
  
    // if server uses '+' for spaces, convert back
    t = t.replace(/\+/g, ' ');
  
    // DO NOT trim — trailing spaces are part of the 9-char board
    return t;
  }
  

  return (
    <div className="app" style={{width:'min(560px,92vw)', margin:'0 auto', color:'#e7eaf3'}}>
      <h1>🎮 Tic-Tac-Toe — You (X) vs Computer (O)</h1>
      <div style={{opacity:.9, margin:'.25rem 0 .75rem', color: err ? '#ff8090' : 'inherit'}}>
        {err ? `Error: ${err}` : status}
      </div>

      <div style={{display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:'10px'}}>
        {board.map((m, i) => (
          <button key={i}
                  onClick={() => play(i)}
                  disabled={thinking || /* cell occupied? */ (m !== ' ') || winner(board)}
                  style={{
                    aspectRatio:'1/1',
                    border:0, borderRadius:'16px',
                    background:'#131a33', color:'#e7eaf3',
                    fontSize:'3rem', fontWeight:800, cursor:'pointer'
                  }}>
            {m.toUpperCase()}
          </button>
        ))}
      </div>

      <div style={{marginTop:'1rem'}}>
        <button onClick={reset}
                style={{padding:'.65rem .9rem', borderRadius:'12px', background:'#1f2a4d', color:'#e7eaf3', fontWeight:700}}>
          Reset
        </button>
      </div>
    </div>
  );
}
