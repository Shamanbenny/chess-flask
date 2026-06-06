# Stockfish UCI_Elo and Skill Level

## Executive Summary

This report explains Stockfish’s **UCI_Elo** and **Skill Level** options for limiting engine strength, how they work, and how they interact with other UCI engine settings. Official Stockfish documentation and the UCI protocol clarify that **`UCI_LimitStrength`** (a Boolean option) turns on strength limiting, and **`UCI_Elo`** (a spin option) sets the target Elo when limiting. If limiting is enabled, Stockfish converts the desired Elo into an internal “skill level” (0–20) and purposely plays suboptimally by choosing weaker moves at low search depths. The **Skill Level** (0–20) can also be set directly without turning on `UCI_LimitStrength`. Lower skill values force Stockfish to pick from *at least four* candidate moves (via MultiPV) and add a random bias favoring weaker moves. In practice, lower skill or Elo targets produce weaker play (e.g. skill 0 ≈ ~1300–1400 Elo) whereas skill 20 or no limit yields full strength (≈3000+ Elo on modern hardware).  

We cover **usage caveats and reproducibility tips**, including how multi-threading, hash size, tablebases, pondering, and GUI behaviors affect effective strength. We provide a **configuration table** (with at least 8 examples) mapping settings to approximate Elo ranges, and a *decision flowchart* for choosing settings given a target Elo. Official Stockfish docs and UCI specs are cited, supplemented by community-tested advice (e.g. Arena GUI behavior) where relevant. (Unless stated, assume “unspecified” means a recent Stockfish build, e.g. SF 17/18 on a modern multi-core CPU.)  

## UCI_LimitStrength, UCI_Elo and Skill Level

Stockfish (and other UCI engines) expose a **`UCI_LimitStrength`** checkbox (default *false*) and a **`UCI_Elo`** spin control (default 1320, min 1320, max 3190 in older docs) as per the UCI spec.  When `UCI_LimitStrength = true`, the engine **“aims for an engine strength of the given Elo”**. In Stockfish, this Elo value is calibrated at a fixed time control (120 s+1 s) and tied to CCRL ratings. Official docs note that `UCI_LimitStrength` **overrides** the Skill Level setting. In other words, *if* limit-strength is on, the `UCI_Elo` setting *replaces* Skill Level. If `UCI_LimitStrength = false`, the `UCI_Elo` value is ignored by Stockfish.

The **Skill Level** option (spin 0–20, default 20) independently reduces strength by making Stockfish choose suboptimal moves. Lowering Skill Level causes Stockfish to “play weaker” even with `UCI_LimitStrength = false`, by using a randomized bias on slightly worse candidate moves. Internally, Stockfish ensures at least four candidate moves (via the MultiPV mechanism) and then randomly boosts the scores of non-best moves; at lower skill the chance of skipping the top move increases. The engine selects the suboptimal move at a search depth of `1 + Skill_Level` (e.g. depth 1 for skill 0, depth 11 for skill 10). In short, **`Skill Level = 20` (default) yields full strength; `Skill = 0` yields roughly ~1300–1400 Elo** in practice. Intermediate skill settings produce intermediate Elo. As one source reports, skill 0 maps to ~1347 Elo and skill 10 to ~2264 Elo (with skill 19 ≈ 2886 Elo).

Key points:

- **UCI_LimitStrength (Boolean)**: OFF = no limit (ignore UCI_Elo). ON = limit strength to `UCI_Elo`. Overrides Skill Level.
- **UCI_Elo (spin)**: Target rating when limit is on. If `UCI_LimitStrength = false`, this is ignored. Otherwise the engine “aims for” that Elo. Officially calibrated on slow time control (2m+1s) against CCRL.
- **Skill Level (spin 0–20)**: Decreases playing strength by choice of suboptimal moves. Lower = weaker. Internally forces MultiPV≥4 and random bias on move scores.

## How Weakened Play Works

Both methods weaken play **by choosing inferior moves**, not by reducing search time. Stockfish first generates a set of top candidate moves (minimum 4 moves; higher if MultiPV is set higher). It then adds a random bias to the evaluation scores of the second-, third-, etc. best moves. A low skill setting gives a large bias, making the engine likely to **bypass the true best move**. The random pick occurs at a shallow search depth (depth = 1+Skill_Level). For example, at Skill=0 Stockfish will often make a mistake as early as depth=1, whereas at Skill=20 (full strength) no such bias is used. 

When using **UCI_Elo with LimitStrength**, Stockfish internally converts the Elo to a corresponding Skill Level (so in effect both operate on the same mechanism). Thus, e.g. setting UCI_Elo≈1500 produces a very low skill internally (around 1–2) and mostly random opening play, whereas UCI_Elo≈2500 yields a high skill (perhaps ~8–12) for near master-level play. The exact conversion is not linear, but calibration data suggests, for instance, Skill 0 ≈ 1347 Elo, Skill 5 ≈ 1871 Elo, Skill 10 ≈ 2264 Elo, Skill 15 ≈ 2619 Elo, and Skill 19 ≈ 2886 Elo. (Default Skill=20 would be even stronger, effectively the engine’s full 3000+ Elo on fast hardware.) 

Stockfish outputs its chosen (weak) move as usual. If you enable `UCI_ShowWDL`, you’ll see Win/Draw/Loss probabilities adjusted to the weaker play (but the *move choice* itself is determined by the above process). In tournament or match play, **ensure you enable `UCI_LimitStrength` _before_ setting `UCI_Elo`**; as one user noted, simply sending `setoption name UCI_Elo value 800` without `LimitStrength=true` will be ignored. (After setting options via UCI, always send `isready` and wait for `readyok` before play begins.)

## Interaction with Other UCI Options

Stockfish has many UCI options; most do **not** directly disable or override the strength-limit settings, but can affect effective strength. Key interactions:

- **Threads and Hash**: These control search speed. More threads and larger hash yield stronger play (faster deeper search) but don’t change the *strategy* of picking moves. For maximum reproducibility, set `Threads` to the number of CPU cores (or fewer if multitasking) and set `Hash` (in MB) according to available RAM. For example, 1 thread with a small hash is slower and slightly weaker than 8 threads with a big hash on the same machine. However, **UCI_LimitStrength/Elo and Skill always apply regardless of threads/hash**; they modify the choice of moves, not how fast the engine runs. (In practice a weaker hardware/less time scenario may prevent the engine from reaching the depth where it would normally force a mistake, adding variance to the resulting Elo.) 

- **MultiPV**: This normally controls how many principal variations (PV) are searched (for analysis). For playing, Stockfish’s Skill mechanism *enables MultiPV internally* to at least 4 (the number of candidate moves). In fact, it ignores any MultiPV setting below 4; if you set `MultiPV=1`, Stockfish will still generate 4 move candidates for skill-level calculations. If you set `MultiPV>4`, it can consider even more moves to pick from (possibly making weaker play even more random). In short, don’t rely on setting MultiPV to 1 to disable the skill behavior – the skill algorithm enforces its own MultiPV ≥4.

- **Contempt**: (An evaluation bias parameter common in older engines.) Stockfish **no longer includes a user-settable Contempt option in modern NNUE versions**. A recent patch removed the UCI Contempt option, effectively fixing it at 0. Thus, there is no user-accessible Contempt parameter to tweak – it does not affect UCI_Elo/Skill behavior in current Stockfish. (Older “Classical” builds had Contempt, but these are deprecated.)

- **Syzygy Tablebases**: Enabling Syzygy (via `SyzygyPath`, etc.) gives perfect endgame play for few pieces. If Skill or Elo-limiting is on, Stockfish will *still* use tablebases for positions within the probe limit (up to N pieces), essentially playing flawlessly there. In practice, tablebase use only affects deep endgames with few pieces. It usually *increases* strength slightly (finding exact wins/draws); one test found only ~2 Elo gain from TBs. Tablebase settings (probe depth, path) should be set normally; they do not need to be turned off for limiting strength, but be aware that they give perfect endgames which might exceed your target strength. 

- **Ponder**: If `Ponder=true`, Stockfish thinks on the opponent’s time as well. This effectively gives the engine **more time per move on average**, making it slightly stronger (or consistent) than without pondering. Pondering does *not* interfere with UCI_Elo/Skill – the engine still picks weaker moves according to skill level – but it may reach those decisions faster. In match settings, turning ponder off is common so each side uses equal time. 

- **Move Overhead**: `Move Overhead` (default 10ms) just tells Stockfish to reserve some time per move for GUI or network delay. It doesn’t affect strength except in blitz games: insufficient overhead might cause time forfeits. For playing at limited strength under time controls, set overhead to your GUI’s round-trip latency to avoid time trouble. This doesn’t interact with Elo/Skill logic directly, but is important for realistic time management.

- **Other UCI Options**: Things like `UCI_Chess960`, `UCI_ShowWDL`, or debug logging do not affect strength. Chess960 is handled by the GUI position only. Using an **opening book** (in your GUI) can dramatically affect strength—if you always play the best book moves, even a weak engine looks strong. For Elo-limited play, you may want *no book*, or a weak book, to match real Elo conditions. Similarly, custom NNUE networks or evaluation files can change playing style or strength; stick to defaults unless you know what you’re doing.

## Using Strength Limiting in GUIs

In chess GUIs (Arena, CuteChess, ChessBase, etc.), you typically set these options in the Engine/Engine Management dialog. Be aware of how each GUI handles them:

- **Arena Chess GUI**: Arena shows an *informative* “Engine Elo” field but it **does not control strength**. You must set the engine’s Skill Level or UCI_LimitStrength/Elo via `Ctrl+1` (Engine params) or the engine’s options dialog. As one user noted: “You can't set Stockfish to play at a given Elo level. If you want to weaken it, change the Skill Level... ‘0’ is the weakest setting and ... ‘20’ means full strength”. You may also enter your own “Rating” in the Engine management details (F11), but that only changes the displayed label (defaults to 2000), not actual play. To ensure effect, check that after changing settings you start a *new game* in Arena (or send a newgame/UCI commands via another GUI) so the engine resets its hash and parameters.

- **CuteChess and Other Test GUIs**: CuteChess (and similar) allow you to add engines and set UCI options directly. Here you can enable `UCI_LimitStrength` and set `UCI_Elo` to a target. Or you can set `Skill Level`. Ensure that “Start new game after setting options” is invoked, or manually send `ucinewgame/isready`, or simply restart the engine. CuteChess also supports multi-engine matches, so for reproducibility you should fix seeds or disable parallel search between games.

- **ChessBase and Fritz GUI**: In CB’s “Engine-Engine” or “Play vs Computer” dialogs, you can click “Engine parameter” and find the Skill Level or Elo slider (depending on engine build). In older Fritz executables you might see “ELO strength” settings. Stockfish if added as a UCI engine will show Skill Level; some builds might show “Tournament level (ELO)” if compiled with `USE_ELO`. The interface often lets you set an Elo target (with LimitStrength) directly in the engine’s options. **Note**: if using a Stockfish engine with a graphical GUI like ChessBase, make sure `UCI_LimitStrength=true` whenever you set an Elo. Some GUIs may ignore Elo unless LimitStrength is checked.

- **Engine Versions and Differences**: Some very old Stockfish versions (pre-2019) did not implement UCI_Elo. In that case only Skill Level works. Newer Stockfish uses NNUE and fixed the Contempt, as noted above. If you see an option for “Weakening” or “Tournament strength” instead of Elo, it may be a GUI-specific feature (e.g. Dragon engine had “Tournament Elo”, not native UCI). Always verify the engine options list after launching (via `uci` and parsing its `option name ...` lines) to see what controls you have. 

### Assumptions

- **Stockfish Version**: Unless otherwise specified, assume a modern Stockfish (NNUE) build (e.g. 16–18). Old SF (versions ≤11) differ: older SF used hand-crafted eval, had a Contempt option, and min skill-level Elo was ~1100. The tables below and advice assume NNUE-era (skill 0 ≈1350 Elo). 
- **Hardware**: The listed Elo ranges assume a decently fast CPU. On a slow or single-core device, the engine will perform weaker (especially at higher skill). Conversely, on very fast or many-core machines, it may exceed calibrated Elo for a given skill. For strict Elo calibration one should use the same conditions as CCRL (which was roughly a 40/4 time control on a mid-range CPU, single-threaded). Our examples use multi-thread (4–8) and 64–512 MB hash to approximate modern use, but the Elo ranges carry “±” since your hardware/time matters. 
- **Time Control / Depth**: Elo calibrations are time-sensitive. Stockfish’s UCI_Elo is calibrated at 2m+1s. If you play shorter games, expect slightly lower strength; longer time may give a small increase. For example configurations below, we suggest typical blitz/rapid time controls or fixed depth. But actual Elo can vary by ±50–100 based on time. 

## Configuration Examples (Settings ⇒ Estimated Elo)

Below is a **comparative table** of example Stockfish configurations, ranging from very weak to maximum. All examples use Stockfish NNUE (unspecified exact version). Columns include whether limit-strength is enabled, the Elo or skill settings, thread and hash usage, a recommended time control or depth (for testing), and the **expected Elo range** (with rough confidence). The Elo ranges are *estimates* based on the above calibrations and community data. Actual results may differ on your hardware or with different time controls.

| Stockfish ver.  | LimitStrength | UCI_Elo | Skill | Threads | Hash (MB) | Time Control / Depth        | Expected Elo (approx.)      | Notes / Caveats                   |
|-----------------|---------------|---------|-------|---------|-----------|-----------------------------|-----------------------------|-----------------------------------|
| Unspecified     | **True**      | 1350    | –     | 1       | 16        | 30+0 (bullet) / or depth 5  | ~~1300–1400 (±100)          | **Very weak**. Skill=0 level (≈1350 Elo). Suitable for beginners. MultiPV forces 4 moves with heavy bias. |
| Unspecified     | **False**     | –       | 0     | 1       | 16        | 30+0 / or depth 5           | ~~1300–1400 (±100)          | Skill=0 (min). Similar strength to above. Use this if GUI ignores UCI_Elo.           |
| Unspecified     | **True**      | 1800    | –     | 4       | 64        | 120+1 / or depth 12         | ~~1700–1900 (±100)          | Weak club player strength. (LS overrides skill.) |
| Unspecified     | **False**     | –       | 5     | 4       | 64        | 120+1 / or depth 12         | ~~1800–1950 (±75)           | Skill=5 (~1871 Elo). Multi-thread and decent hash. |
| Unspecified     | **True**      | 2200    | –     | 4       | 64        | 300+5 / or depth 15         | ~~2100–2300 (±100)          | Advanced club / CM level. |
| Unspecified     | **False**     | –       | 10    | 8       | 256       | 300+5 / or depth 20         | ~~2700–2850 (±100)          | Skill=10 (~2264 Elo, but deep search + threads raise effective strength). |
| Unspecified     | **False**     | –       | 15    | 8       | 256       | 600+10 / infinite depth     | ~~2900+                    | Skill=15 (~2619 Elo). With long time, engine approaches its best play (≈3100 in engine terms). |
| Unspecified     | **False**     | –       | 20    | Max     | Max       | 600+10 / infinite depth     | ~~3000+ (full strength)     | Skill=20 = full strength. Use all cores/hash. This is essentially engine limit. |
| Unspecified     | **True**      | 3000    | –     | Max     | Max       | 600+10 / infinite depth     | ~~2900–3000 (±50)           | High Elo cap. Even with LS on, setting Elo very high yields max strength (same as skill 20). |

- *Column notes*: “–” in UCI_Elo/Skill means that option is ignored (e.g. when LimitStrength is false, UCI_Elo is unused). Threads=Max means use all available cores (or number input); Hash=Max means a large hash such as 512 MB or more (subject to system RAM). Time control *“X+Y”* means X seconds base with Y seconds increment; **Depth** means a fixed search ply. 
- The **Expected Elo** ranges are approximate. For weak settings (rows 1–4), confidence is lower because short time/depth and randomness cause wide spread (engine may stalemate often, etc.). For strong settings, ranges are “>3000” since Stockfish’s engine Elo is beyond human ratings. 
- **Notes**: Row 1 is similar to row 2 but explicitly uses UCI_Elo=1350. Row 6 shows that even skill 10 (≈2264 Elo) under deep search and multi-threading can play around 2700+. Row 8 is full strength: even humans rate GM engine Elo as “infinite”, but CCRL reports ~3500 and CCRL‐to‐FIDE formulas put it >2900. Row 9 illustrates that setting UCI_Elo very high essentially disables limiting (Skill=20). 
- All examples assume modern Stockfish; older versions had different skill curves (e.g. SF7 skill0 was ~1240 Elo on some hardware).

## Usage Tips and Caveats

- **Reproducibility**: To get consistent results, *fix threads, hash, time control/depth, and disable ponder and other sources of variability*. Use an engine-testing GUI (like CuteChess or CCRL framework) with fixed randomness if benchmarking. Sending the sequence `uci` → setoptions → `isready` → `ucinewgame` before each match ensures a cold start (cleared hash).  
- **Time Settings**: Stronger play occurs with more thinking time. The UCI_Elo calibration assumes 2m+1s; in blitz (say 30+0) the effective Elo will drop ~50–100 points below target. For accurate Elo games, use a relatively slow control or add an increment.  
- **Opening Book**: If you want the engine to play at its announced Elo, *do not use a strong opening book*. Unlimited book play would inflate its wins. Conversely, you can simulate weaker opponents by forcing book moves.  
- **Skill vs Elo Mode**: Use `UCI_LimitStrength`+`UCI_Elo` if you need precise Elo targeting and if the GUI supports it. Otherwise use Skill Level. Note: Skill is quantized (21 levels), so it can only approximate Elo. For example, if you set UCI_Elo=1500, Stockfish might actually play at about Skill 1–2 (≈1400–1500 Elo).  
- **Lower-Bound**: Stockfish’s lowest playable strength is around 1300–1350 Elo. You cannot get it down to beginner ELO (e.g. 1000); the engine will still make mostly legal, mildly sensible moves. (For ultralow strength, some use “dumb” engines or random playouts outside UCI.)  
- **Human-Like Play**: The Skill mechanism does not mimic human blundering. It simply picks another engine-chosen move. Games will often be strangely “engine-like but weaker”, not truly human style. There is no built-in “error probability based on blunder rate” except the depth=bias mechanism already described.  

## Decision Flowchart

The following flowchart illustrates how to choose Stockfish settings for a desired Elo:

```mermaid
flowchart TD
    A[Start: Desired Elo] --> B{>= 1350?}
    B -- No --> C[Target too low (Skill 0 ≈ 1347 Elo).\nUse Skill 0 (or external help).]
    B -- Yes --> D{Engine supports UCI_Elo?}
    D -- Yes --> E[Enable UCI_LimitStrength=TRUE]
    E --> F[Set UCI_Elo = target Elo\n(Check bounds 1350–3190).]
    F --> G{Elo > max?}
    G -- Yes --> H[Set skill=20 (max strength).]
    G -- No --> I[Engine will convert Elo to Skill.]
    D -- No --> J[Use Skill Level mode instead]
    J --> K[Convert target Elo to Skill (approx).\nSet Skill Level.]
    I --> L[Set threads, hash, time as needed\nand play.]
    H --> L
    K --> L
    C --> L
    style C fill:#f9f,stroke:#333,stroke-width:2px
    style H fill:#f9f,stroke:#333,stroke-width:2px
```

This decision flow assumes Stockfish (NNUE) where min Elo≈1350. If using a version without `UCI_Elo`, skip straight to Skill (node J). In practice, if the desired Elo is below skill 0 or above skill 20, you hit the lower/upper limits (pink boxes). Otherwise, enabling `UCI_LimitStrength` and setting `UCI_Elo` is simplest; Stockfish will internally map that Elo to a skill level and play accordingly. 

## Sources and Further Reading

- Official **Stockfish documentation (UCI & commands)** describing these options and behavior. The FAQ explicitly explains how Skill/Elo produce weaker play.  
- The **UCI protocol specification** (by David Murray and others) mandates the `UCI_LimitStrength` and `UCI_Elo` options: if strength-limiting is off, the Elo is ignored.  
- Community Q&A (StackExchange, TalkChess, Reddit) for calibration data and GUI notes. Arena users and others confirm that the GUI’s displayed “rating” is separate from Stockfish’s playing strength.  
- Usage tips on threads/hash come from Stockfish docs and Fishtest advice. Contempt removal is documented in the Stockfish Git commit.  
- For reproducibility, consider using a testing GUI like CuteChess and fixing all parameters. The ranges above should be viewed as *estimates*. The best way to know your setup’s strength is to play matches against a known reference or use official test suites (e.g. CCRL) under controlled conditions. 

