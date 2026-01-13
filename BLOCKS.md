 8421 +     PatternBlock(
      8422 +         id="BOS_DOWN",
      8423 +         name="Break of Structure Down",
      8424 +         category="structure_break",
      8425 +         formula_template="""df['swing_low'] = df['low'].rolling({period}).min().shift(1)
      8426 + df['break'] = df['close'] < df['swing_low']
      8427 + df['strong_break'] = df['close'] < df['swing_low'] * (1 - {margin})
      8428 + df['entry_signal'] = df['strong_break']""",
      8429 +         params={"period": [10, 20], "margin": [0.001, 0.002]},
      8430 +         direction="short",
      8431 +         lookback=30,
      8432 +         indicators=[],
      8433 +         combinable_with=["volume", "momentum", "confirmation"],
      8434 +         strategy_type="STB",
      8435 +     ),
      8436 +     # Change of Character (CHoCH)
      8437 +     PatternBlock(
      8438 +         id="CHOCH_BULL",
      8439 +         name="Change of Character Bullish",
      8440 +         category="structure_break",
      8441 +         formula_template="""df['prev_low'] = df['low'].rolling({period}).min()
      8442 + df['made_lower_low'] = df['low'] < df['prev_low'].shift(1)
      8443 + df['now_higher_high'] = df['high'] > df['high'].shift(1)
      8444 + df['reversal'] = df['made_lower_low'].shift(1) & df['now_higher_high']
      8445 + df['entry_signal'] = df['reversal']""",
      8446 +         params={"period": [10, 20]},
      8447 +         direction="long",
      8448 +         lookback=30,
      8449 +         indicators=[],
      8450 +         combinable_with=["volume", "confirmation"],
      8451 +         strategy_type="STB",
      8452 +     ),
      8453 + ]
      8454 +
      8455 +
      8456 + # =============================================================================
      8457 + # IMPULSE CORRECTION BLOCKS
      8458 + # =============================================================================
      8459 +
      8460 + IMPULSE_CORRECTION_BLOCKS = [
      8461 +     # Impulse move followed by pullback
      8462 +     PatternBlock(
      8463 +         id="IMPULSE_PULLBACK_BULL",
      8464 +         name="Bullish Impulse Pullback",
      8465 +         category="impulse_correction",
      8466 +         formula_template="""df['impulse_move'] = df['close'].shift({pullback}) - df['close'].shift({impulse})
      8467 + df['impulse_pct'] = df['impulse_move'] / df['close'].shift({impulse}) * 100
      8468 + df['had_impulse'] = df['impulse_pct'] > {imp_thresh}
      8469 + df['pullback'] = df['close'] < df['close'].shift({pullback})
      8470 + df['entry_signal'] = df['had_impulse'] & df['pullback']""",
      8471 +         params={"impulse": [10], "pullback": [3], "imp_thresh": [3, 5]},
      8472 +         direction="long",
      8473 +         lookback=20,
      8474 +         indicators=[],
      8475 +         combinable_with=["volume", "threshold", "confirmation"],
      8476 +         strategy_type="IMP",
      8477 +     ),
      8478 +     # Impulse continuation
      8479 +     PatternBlock(
      8480 +         id="IMPULSE_CONTINUE",
      8481 +         name="Impulse Continuation",
      8482 +         category="impulse_correction",
      8483 +         formula_template="""df['move_5'] = (df['close'] - df['close'].shift(5)) / df['close'].shift(5) * 100
      8484 + df['move_1'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
      8485 + df['impulse'] = df['move_5'] > {threshold}
      8486 + df['continues'] = df['move_1'] > 0
      8487 + df['entry_signal'] = df['impulse'] & df['continues']""",
      8488 +         params={"threshold": [3, 5]},
      8489 +         direction="long",
      8490 +         lookback=15,
      8491 +         indicators=[],
      8492 +         combinable_with=["volume", "momentum"],
      8493 +         strategy_type="IMP",
      8494 +     ),
      8495 +     # Correction complete (price resumes)
      8496 +     PatternBlock(
      8497 +         id="CORRECTION_COMPLETE",
      8498 +         name="Correction Complete",
      8499 +         category="impulse_correction",
      8500 +         formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
      8501 + df['swing_low'] = df['low'].rolling({period}).min()
      8502 + df['retrace'] = (df['swing_high'] - df['close']) / (df['swing_high'] - df['swing_low'])
      8503 + df['was_retracing'] = df['retrace'].shift(1) > {retrace_level}
      8504 + df['resuming'] = df['close'] > df['close'].shift(1)
      8505 + df['entry_signal'] = df['was_retracing'] & df['resuming']""",
      8506 +         params={"period": [20], "retrace_level": [0.4, 0.5]},
      8507 +         direction="long",
      8508 +         lookback=30,
      8509 +         indicators=[],
      8510 +         combinable_with=["volume", "confirmation"],
      8511 +         strategy_type="IMP",
      8512 +     ),
      8513 + ]
      8514 +
      8515 +
      8516 + # =============================================================================
      8517   # ALL BLOCKS COMBINED
      8518   # =============================================================================
      8519

 ▐▛███▜▌   Claude Code v2.1.5
▝▜█████▛▘  Opus 4.5 · Claude Max
  ▘▘ ▝▝    ~/sixbtc
══════════════════════════════════════════════════════ Conversation compacted · ctrl+o for history ═════════════════════════════════════════════════════
  ⎿  Referenced file src/generator/pattern_gen/building_blocks.py
  ⎿  Read src/generator/pattern_gen/templates/pattern_gen_strategy.j2 (102 lines)
  ⎿  Read src/generator/pattern_gen/generator.py (449 lines)
  ⎿  Read src/validator/syntax_validator.py (222 lines)
  ⎿  Read .venv/bin/activate (77 lines)
  ⎿  Todo list read (11 items)

● Continuo con l'implementazione del Round 11. Devo ancora aggiornare ALL_BLOCKS per includere i nuovi blocchi e poi validare.

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 200 lines

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 78 lines

● Vedo che ALL_BLOCKS termina con THRUST_BLOCKS. Devo aggiungere i 10 nuovi gruppi di blocchi.

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      8622       + BARS_SINCE_BLOCKS
      8623       + RELATIVE_POSITION_BLOCKS
      8624       + THRUST_BLOCKS
      8625 +     + PIVOT_EXT_BLOCKS
      8626 +     + ATR_BANDS_BLOCKS
      8627 +     + PRICE_CHANGE_RATE_BLOCKS
      8628 +     + VOLUME_DISTRIBUTION_BLOCKS
      8629 +     + TREND_EXHAUSTION_EXT_BLOCKS
      8630 +     + REVERSAL_CANDLE_EXT_BLOCKS
      8631 +     + MA_CONVERGENCE_BLOCKS
      8632 +     + PRICE_RATIO_BLOCKS
      8633 +     + STRUCTURE_BREAK_BLOCKS
      8634 +     + IMPULSE_CORRECTION_BLOCKS
      8635   )
      8636
      8637   # Index by ID for quick lookup

● Ora eseguo la validazione completa.

● Bash(source .venv/bin/activate && python -c "
      from src.generator.pattern_gen.building_blocks import ALL_BLOCKS, BLOCKS_BY_CATEGORY…)
  ⎿  Total blocks: 447
     Categories: 113
     … +23 lines (ctrl+o to expand)

● Round 11 completato!

  Risultati:
  - Blocchi totali: 447 (da 415, +32)
  - Categorie: 113 (da 103, +10)
  - Validazione: 200/200 OK
  - Lookahead: 0 problemi
  - Strategie stimate: ~100,392 (superato i 100k!)

  ---
  Altre possibili migliorie (Round 12)?

  Potrei aggiungere altri 30+ blocchi:

  1. FRACTAL_BLOCKS (3) - Williams fractals up/down per identificare swing points
  2. VOLUME_PROFILE_BLOCKS (3) - Volume at price levels, POC detection
  3. MARKET_DEPTH_BLOCKS (3) - Bid/ask imbalance proxy tramite volume patterns
  4. ZIGZAG_BLOCKS (3) - ZigZag pattern detection per swings
  5. VORTEX_BLOCKS (3) - Vortex indicator VI+/VI- crossovers
  6. MASS_INDEX_BLOCKS (3) - Reversal signals via range expansion
  7. CHANDE_MOMENTUM_BLOCKS (3) - CMO extreme levels e crossover
  8. RANGE_ACTION_BLOCKS (3) - RAVI indicator per trend strength
  9. CONNORS_RSI_BLOCKS (3) - RSI + UpDown Length + ROC combined
  10. SQUEEZE_MOMENTUM_BLOCKS (3) - BB squeeze con momentum direction

  Totale: +30 blocchi → 477 blocchi, ~107,000+ strategie

  Vuoi che implementi?

✻ Brewed for 3m 23s

❯ hai testato che tutto funzioni?
  altre possibili migliorie? con gli stessi requisiti, cioè no modifiche al codice esistente, piena compatibilità, no diminuzione strategie
  dimmi solo

● Sì, testato:
  - 200/200 strategie valide
  - 0 lookahead issues
  - 447 blocchi, 113 categorie
  - ~100,392 strategie stimate

  ---
  Round 12 - Proposte (+32 blocchi):

  1. FRACTAL_BLOCKS (3) - Williams fractals, swing detection
  2. VOLUME_PROFILE_BLOCKS (3) - Volume concentration, POC proxy
  3. ZIGZAG_BLOCKS (3) - Swing high/low pattern detection
  4. VORTEX_BLOCKS (3) - VI+/VI- crossovers e trend
  5. MASS_INDEX_BLOCKS (3) - Range reversal signals
  6. CONNORS_RSI_BLOCKS (3) - Multi-factor RSI composite
  7. SQUEEZE_BLOCKS (3) - BB inside Keltner squeeze
  8. PRICE_TRANSFORM_BLOCKS (3) - Log returns, normalized price
  9. ADAPTIVE_CHANNEL_BLOCKS (3) - Dynamic channel width
  10. MOMENTUM_QUALITY_BLOCKS (4) - Momentum smoothness, acceleration quality

  Totale: +31 blocchi → 478 blocchi, ~108,000+ strategie

  Vuoi che implementi?

❯ si

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 40 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 661 lines
      8514
      8515
      8516   # =============================================================================
      8517 + # FRACTAL BLOCKS - Williams Fractals
      8518 + # =============================================================================
      8519 +
      8520 + FRACTAL_BLOCKS = [
      8521 +     # Fractal High (bearish fractal)
      8522 +     PatternBlock(
      8523 +         id="FRACTAL_HIGH",
      8524 +         name="Fractal High Formed",
      8525 +         category="fractal",
      8526 +         formula_template="""df['mid_high'] = df['high'].shift(2)
      8527 + df['left1'] = df['high'].shift(3) < df['mid_high']
      8528 + df['left2'] = df['high'].shift(4) < df['mid_high']
      8529 + df['right1'] = df['high'].shift(1) < df['mid_high']
      8530 + df['right2'] = df['high'] < df['mid_high']
      8531 + df['fractal_high'] = df['left1'] & df['left2'] & df['right1'] & df['right2']
      8532 + df['entry_signal'] = df['fractal_high']""",
      8533 +         params={},
      8534 +         direction="short",
      8535 +         lookback=10,
      8536 +         indicators=[],
      8537 +         combinable_with=["volume", "confirmation", "momentum"],
      8538 +         strategy_type="FRC",
      8539 +     ),
      8540 +     # Fractal Low (bullish fractal)
      8541 +     PatternBlock(
      8542 +         id="FRACTAL_LOW",
      8543 +         name="Fractal Low Formed",
      8544 +         category="fractal",
      8545 +         formula_template="""df['mid_low'] = df['low'].shift(2)
      8546 + df['left1'] = df['low'].shift(3) > df['mid_low']
      8547 + df['left2'] = df['low'].shift(4) > df['mid_low']
      8548 + df['right1'] = df['low'].shift(1) > df['mid_low']
      8549 + df['right2'] = df['low'] > df['mid_low']
      8550 + df['fractal_low'] = df['left1'] & df['left2'] & df['right1'] & df['right2']
      8551 + df['entry_signal'] = df['fractal_low']""",
      8552 +         params={},
      8553 +         direction="long",
      8554 +         lookback=10,
      8555 +         indicators=[],
      8556 +         combinable_with=["volume", "confirmation", "momentum"],
      8557 +         strategy_type="FRC",
      8558 +     ),
      8559 +     # Fractal Breakout
      8560 +     PatternBlock(
      8561 +         id="FRACTAL_BREAKOUT",
      8562 +         name="Fractal Breakout",
      8563 +         category="fractal",
      8564 +         formula_template="""df['mid_high'] = df['high'].shift(2)
      8565 + df['fh_left1'] = df['high'].shift(3) < df['mid_high']
      8566 + df['fh_right1'] = df['high'].shift(1) < df['mid_high']
      8567 + df['fractal_high'] = df['fh_left1'] & df['fh_right1']
      8568 + df['last_fractal'] = df['mid_high'].where(df['fractal_high']).ffill()
      8569 + df['breakout'] = df['close'] > df['last_fractal'] * (1 + {margin})
      8570 + df['entry_signal'] = df['breakout']""",
      8571 +         params={"margin": [0.001, 0.002]},
      8572 +         direction="long",
      8573 +         lookback=15,
      8574 +         indicators=[],
      8575 +         combinable_with=["volume", "momentum"],
      8576 +         strategy_type="FRC",
      8577 +     ),
      8578 + ]
      8579 +
      8580 +
      8581 + # =============================================================================
      8582 + # VOLUME PROFILE BLOCKS
      8583 + # =============================================================================
      8584 +
      8585 + VOLUME_PROFILE_BLOCKS = [
      8586 +     # High Volume Node
      8587 +     PatternBlock(
      8588 +         id="HIGH_VOLUME_NODE",
      8589 +         name="High Volume Node",
      8590 +         category="volume_profile",
      8591 +         formula_template="""df['vol_ma'] = df['volume'].rolling({period}).mean()
      8592 + df['vol_std'] = df['volume'].rolling({period}).std()
      8593 + df['high_vol'] = df['volume'] > df['vol_ma'] + df['vol_std'] * {mult}
      8594 + df['price_stable'] = abs(df['close'] - df['close'].shift(1)) / df['close'] < 0.005
      8595 + df['entry_signal'] = df['high_vol'] & df['price_stable']""",
      8596 +         params={"period": [20, 50], "mult": [1.5, 2.0]},
      8597 +         direction="bidi",
      8598 +         lookback=60,
      8599 +         indicators=[],
      8600 +         combinable_with=["momentum", "threshold"],
      8601 +         strategy_type="VPR",
      8602 +     ),
      8603 +     # Volume Climax at Support
      8604 +     PatternBlock(
      8605 +         id="VOL_CLIMAX_SUPPORT",
      8606 +         name="Volume Climax at Support",
      8607 +         category="volume_profile",
      8608 +         formula_template="""df['vol_rank'] = df['volume'].rolling({period}).apply(lambda x: (x[-1] - x.min()) / (x.max() - x.min()
           ++ 1e-10), raw=True)
      8609 + df['price_low'] = df['low'] <= df['low'].rolling({period}).min() * 1.01
      8610 + df['vol_extreme'] = df['vol_rank'] > {vol_thresh}
      8611 + df['entry_signal'] = df['vol_extreme'] & df['price_low']""",
      8612 +         params={"period": [20], "vol_thresh": [0.8, 0.9]},
      8613 +         direction="long",
      8614 +         lookback=30,
      8615 +         indicators=[],
      8616 +         combinable_with=["confirmation", "momentum"],
      8617 +         strategy_type="VPR",
      8618 +     ),
      8619 +     # Low Volume Breakout Setup
      8620 +     PatternBlock(
      8621 +         id="LOW_VOL_BREAKOUT_SETUP",
      8622 +         name="Low Volume Breakout Setup",
      8623 +         category="volume_profile",
      8624 +         formula_template="""df['vol_ma'] = df['volume'].rolling({period}).mean()
      8625 + df['low_vol'] = df['volume'] < df['vol_ma'] * {low_mult}
      8626 + df['low_vol_days'] = df['low_vol'].rolling(3).sum() >= 2
      8627 + df['range_tight'] = (df['high'].rolling(3).max() - df['low'].rolling(3).min()) / df['close'] < 0.02
      8628 + df['entry_signal'] = df['low_vol_days'] & df['range_tight']""",
      8629 +         params={"period": [20], "low_mult": [0.5, 0.7]},
      8630 +         direction="bidi",
      8631 +         lookback=30,
      8632 +         indicators=[],
      8633 +         combinable_with=["momentum", "threshold"],
      8634 +         strategy_type="VPR",
      8635 +     ),
      8636 + ]
      8637 +
      8638 +
      8639 + # =============================================================================
      8640 + # ZIGZAG BLOCKS
      8641 + # =============================================================================
      8642 +
      8643 + ZIGZAG_BLOCKS = [
      8644 +     # ZigZag Swing Low
      8645 +     PatternBlock(
      8646 +         id="ZIGZAG_SWING_LOW",
      8647 +         name="ZigZag Swing Low",
      8648 +         category="zigzag",
      8649 +         formula_template="""df['swing_low'] = df['low'].rolling({period}).min()
      8650 + df['is_swing'] = df['low'] == df['swing_low']
      8651 + df['swing_confirmed'] = df['is_swing'].shift({confirm}) & (df['close'] > df['low'].shift({confirm}))
      8652 + df['entry_signal'] = df['swing_confirmed']""",
      8653 +         params={"period": [10, 20], "confirm": [2, 3]},
      8654 +         direction="long",
      8655 +         lookback=30,
      8656 +         indicators=[],
      8657 +         combinable_with=["volume", "momentum", "confirmation"],
      8658 +         strategy_type="ZZG",
      8659 +     ),
      8660 +     # ZigZag Swing High
      8661 +     PatternBlock(
      8662 +         id="ZIGZAG_SWING_HIGH",
      8663 +         name="ZigZag Swing High",
      8664 +         category="zigzag",
      8665 +         formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
      8666 + df['is_swing'] = df['high'] == df['swing_high']
      8667 + df['swing_confirmed'] = df['is_swing'].shift({confirm}) & (df['close'] < df['high'].shift({confirm}))
      8668 + df['entry_signal'] = df['swing_confirmed']""",
      8669 +         params={"period": [10, 20], "confirm": [2, 3]},
      8670 +         direction="short",
      8671 +         lookback=30,
      8672 +         indicators=[],
      8673 +         combinable_with=["volume", "momentum", "confirmation"],
      8674 +         strategy_type="ZZG",
      8675 +     ),
      8676 +     # ZigZag Higher Low
      8677 +     PatternBlock(
      8678 +         id="ZIGZAG_HIGHER_LOW",
      8679 +         name="ZigZag Higher Low",
      8680 +         category="zigzag",
      8681 +         formula_template="""df['swing_low'] = df['low'].rolling({period}).min()
      8682 + df['prev_swing'] = df['swing_low'].shift({period})
      8683 + df['higher_low'] = df['swing_low'] > df['prev_swing']
      8684 + df['confirmed'] = df['close'] > df['close'].shift(1)
      8685 + df['entry_signal'] = df['higher_low'] & df['confirmed']""",
      8686 +         params={"period": [10, 15]},
      8687 +         direction="long",
      8688 +         lookback=40,
      8689 +         indicators=[],
      8690 +         combinable_with=["volume", "confirmation"],
      8691 +         strategy_type="ZZG",
      8692 +     ),
      8693 + ]
      8694 +
      8695 +
      8696 + # =============================================================================
      8697 + # VORTEX BLOCKS
      8698 + # =============================================================================
      8699 +
      8700 + VORTEX_BLOCKS = [
      8701 +     # Vortex Bullish Cross
      8702 +     PatternBlock(
      8703 +         id="VORTEX_BULL_CROSS",
      8704 +         name="Vortex Bullish Cross",
      8705 +         category="vortex",
      8706 +         formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)),
           +abs(df['low'] - df['close'].shift(1))))
      8707 + df['vmp'] = abs(df['high'] - df['low'].shift(1))
      8708 + df['vmm'] = abs(df['low'] - df['high'].shift(1))
      8709 + df['vmp_sum'] = df['vmp'].rolling({period}).sum()
      8710 + df['vmm_sum'] = df['vmm'].rolling({period}).sum()
      8711 + df['tr_sum'] = df['tr'].rolling({period}).sum()
      8712 + df['vip'] = df['vmp_sum'] / df['tr_sum']
      8713 + df['vim'] = df['vmm_sum'] / df['tr_sum']
      8714 + df['cross_up'] = (df['vip'] > df['vim']) & (df['vip'].shift(1) <= df['vim'].shift(1))
      8715 + df['entry_signal'] = df['cross_up']""",
      8716 +         params={"period": [14, 21]},
      8717 +         direction="long",
      8718 +         lookback=30,
      8719 +         indicators=[],
      8720 +         combinable_with=["volume", "threshold", "confirmation"],
      8721 +         strategy_type="VTX",
      8722 +     ),
      8723 +     # Vortex Bearish Cross
      8724 +     PatternBlock(
      8725 +         id="VORTEX_BEAR_CROSS",
      8726 +         name="Vortex Bearish Cross",
      8727 +         category="vortex",
      8728 +         formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)),
           +abs(df['low'] - df['close'].shift(1))))
      8729 + df['vmp'] = abs(df['high'] - df['low'].shift(1))
      8730 + df['vmm'] = abs(df['low'] - df['high'].shift(1))
      8731 + df['vmp_sum'] = df['vmp'].rolling({period}).sum()
      8732 + df['vmm_sum'] = df['vmm'].rolling({period}).sum()
      8733 + df['tr_sum'] = df['tr'].rolling({period}).sum()
      8734 + df['vip'] = df['vmp_sum'] / df['tr_sum']
      8735 + df['vim'] = df['vmm_sum'] / df['tr_sum']
      8736 + df['cross_down'] = (df['vip'] < df['vim']) & (df['vip'].shift(1) >= df['vim'].shift(1))
      8737 + df['entry_signal'] = df['cross_down']""",
      8738 +         params={"period": [14, 21]},
      8739 +         direction="short",
      8740 +         lookback=30,
      8741 +         indicators=[],
      8742 +         combinable_with=["volume", "threshold", "confirmation"],
      8743 +         strategy_type="VTX",
      8744 +     ),
      8745 +     # Vortex Strong Trend
      8746 +     PatternBlock(
      8747 +         id="VORTEX_STRONG_TREND",
      8748 +         name="Vortex Strong Trend",
      8749 +         category="vortex",
      8750 +         formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)),
           +abs(df['low'] - df['close'].shift(1))))
      8751 + df['vmp'] = abs(df['high'] - df['low'].shift(1))
      8752 + df['vmm'] = abs(df['low'] - df['high'].shift(1))
      8753 + df['vmp_sum'] = df['vmp'].rolling({period}).sum()
      8754 + df['vmm_sum'] = df['vmm'].rolling({period}).sum()
      8755 + df['tr_sum'] = df['tr'].rolling({period}).sum()
      8756 + df['vip'] = df['vmp_sum'] / df['tr_sum']
      8757 + df['vim'] = df['vmm_sum'] / df['tr_sum']
      8758 + df['strong_bull'] = (df['vip'] - df['vim']) > {threshold}
      8759 + df['entry_signal'] = df['strong_bull']""",
      8760 +         params={"period": [14], "threshold": [0.2, 0.3]},
      8761 +         direction="long",
      8762 +         lookback=25,
      8763 +         indicators=[],
      8764 +         combinable_with=["momentum", "confirmation"],
      8765 +         strategy_type="VTX",
      8766 +     ),
      8767 + ]
      8768 +
      8769 +
      8770 + # =============================================================================
      8771 + # MASS INDEX BLOCKS
      8772 + # =============================================================================
      8773 +
      8774 + MASS_INDEX_BLOCKS = [
      8775 +     # Mass Index Reversal Bulge
      8776 +     PatternBlock(
      8777 +         id="MASS_INDEX_BULGE",
      8778 +         name="Mass Index Reversal Bulge",
      8779 +         category="mass_index",
      8780 +         formula_template="""df['range'] = df['high'] - df['low']
      8781 + df['ema_range'] = ta.EMA(df['range'], timeperiod=9)
      8782 + df['double_ema'] = ta.EMA(df['ema_range'], timeperiod=9)
      8783 + df['ratio'] = df['ema_range'] / (df['double_ema'] + 1e-10)
      8784 + df['mass'] = df['ratio'].rolling(25).sum()
      8785 + df['bulge'] = (df['mass'].shift(1) > {upper}) & (df['mass'] < {upper})
      8786 + df['entry_signal'] = df['bulge']""",
      8787 +         params={"upper": [26.5, 27.0]},
      8788 +         direction="bidi",
      8789 +         lookback=50,
      8790 +         indicators=["EMA"],
      8791 +         combinable_with=["momentum", "confirmation"],
      8792 +         strategy_type="MAS",
      8793 +     ),
      8794 +     # Mass Index Low (trending)
      8795 +     PatternBlock(
      8796 +         id="MASS_INDEX_LOW",
      8797 +         name="Mass Index Low Trend",
      8798 +         category="mass_index",
      8799 +         formula_template="""df['range'] = df['high'] - df['low']
      8800 + df['ema_range'] = ta.EMA(df['range'], timeperiod=9)
      8801 + df['double_ema'] = ta.EMA(df['ema_range'], timeperiod=9)
      8802 + df['ratio'] = df['ema_range'] / (df['double_ema'] + 1e-10)
      8803 + df['mass'] = df['ratio'].rolling(25).sum()
      8804 + df['low_mass'] = df['mass'] < {lower}
      8805 + df['uptrend'] = df['close'] > df['close'].shift(5)
      8806 + df['entry_signal'] = df['low_mass'] & df['uptrend']""",
      8807 +         params={"lower": [24.0, 24.5]},
      8808 +         direction="long",
      8809 +         lookback=50,
      8810 +         indicators=["EMA"],
      8811 +         combinable_with=["momentum", "threshold"],
      8812 +         strategy_type="MAS",
      8813 +     ),
      8814 +     # Mass Index Setup (before reversal)
      8815 +     PatternBlock(
      8816 +         id="MASS_INDEX_SETUP",
      8817 +         name="Mass Index Setup",
      8818 +         category="mass_index",
      8819 +         formula_template="""df['range'] = df['high'] - df['low']
      8820 + df['ema_range'] = ta.EMA(df['range'], timeperiod=9)
      8821 + df['double_ema'] = ta.EMA(df['ema_range'], timeperiod=9)
      8822 + df['ratio'] = df['ema_range'] / (df['double_ema'] + 1e-10)
      8823 + df['mass'] = df['ratio'].rolling(25).sum()
      8824 + df['rising'] = df['mass'] > df['mass'].shift(1)
      8825 + df['near_bulge'] = df['mass'] > {trigger}
      8826 + df['entry_signal'] = df['rising'] & df['near_bulge']""",
      8827 +         params={"trigger": [25.5, 26.0]},
      8828 +         direction="bidi",
      8829 +         lookback=50,
      8830 +         indicators=["EMA"],
      8831 +         combinable_with=["volume", "confirmation"],
      8832 +         strategy_type="MAS",
      8833 +     ),
      8834 + ]
      8835 +
      8836 +
      8837 + # =============================================================================
      8838 + # CONNORS RSI BLOCKS
      8839 + # =============================================================================
      8840 +
      8841 + CONNORS_RSI_BLOCKS = [
      8842 +     # Connors RSI Oversold
      8843 +     PatternBlock(
      8844 +         id="CONNORS_RSI_OVERSOLD",
      8845 +         name="Connors RSI Oversold",
      8846 +         category="connors_rsi",
      8847 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=3)
      8848 + df['streak'] = (df['close'] > df['close'].shift(1)).astype(int)
      8849 + df['streak'] = df['streak'].replace(0, -1)
      8850 + df['streak_count'] = df['streak'].groupby((df['streak'] != df['streak'].shift()).cumsum()).cumcount() + 1
      8851 + df['streak_count'] = df['streak_count'] * df['streak']
      8852 + df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
      8853 + df['roc_rank'] = df['roc'].rolling({period}).apply(lambda x: (x < x[-1]).sum() / len(x) * 100, raw=True)
      8854 + df['crsi'] = (df['rsi'] + df['roc_rank'] + 50) / 3
      8855 + df['oversold'] = df['crsi'] < {level}
      8856 + df['entry_signal'] = df['oversold']""",
      8857 +         params={"period": [100], "level": [15, 20]},
      8858 +         direction="long",
      8859 +         lookback=120,
      8860 +         indicators=["RSI"],
      8861 +         combinable_with=["volume", "confirmation"],
      8862 +         strategy_type="CRS",
      8863 +     ),
      8864 +     # Connors RSI Overbought
      8865 +     PatternBlock(
      8866 +         id="CONNORS_RSI_OVERBOUGHT",
      8867 +         name="Connors RSI Overbought",
      8868 +         category="connors_rsi",
      8869 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=3)
      8870 + df['streak'] = (df['close'] > df['close'].shift(1)).astype(int)
      8871 + df['streak'] = df['streak'].replace(0, -1)
      8872 + df['streak_count'] = df['streak'].groupby((df['streak'] != df['streak'].shift()).cumsum()).cumcount() + 1
      8873 + df['streak_count'] = df['streak_count'] * df['streak']
      8874 + df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
      8875 + df['roc_rank'] = df['roc'].rolling({period}).apply(lambda x: (x < x[-1]).sum() / len(x) * 100, raw=True)
      8876 + df['crsi'] = (df['rsi'] + df['roc_rank'] + 50) / 3
      8877 + df['overbought'] = df['crsi'] > {level}
      8878 + df['entry_signal'] = df['overbought']""",
      8879 +         params={"period": [100], "level": [80, 85]},
      8880 +         direction="short",
      8881 +         lookback=120,
      8882 +         indicators=["RSI"],
      8883 +         combinable_with=["volume", "confirmation"],
      8884 +         strategy_type="CRS",
      8885 +     ),
      8886 +     # Connors RSI Mean Reversion
      8887 +     PatternBlock(
      8888 +         id="CONNORS_RSI_MEAN_REV",
      8889 +         name="Connors RSI Mean Reversion",
      8890 +         category="connors_rsi",
      8891 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=3)
      8892 + df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
      8893 + df['roc_rank'] = df['roc'].rolling({period}).apply(lambda x: (x < x[-1]).sum() / len(x) * 100, raw=True)
      8894 + df['crsi'] = (df['rsi'] + df['roc_rank'] + 50) / 3
      8895 + df['was_oversold'] = df['crsi'].shift(1) < {low}
      8896 + df['recovering'] = df['crsi'] > df['crsi'].shift(1)
      8897 + df['entry_signal'] = df['was_oversold'] & df['recovering']""",
      8898 +         params={"period": [100], "low": [20, 25]},
      8899 +         direction="long",
      8900 +         lookback=120,
      8901 +         indicators=["RSI"],
      8902 +         combinable_with=["momentum", "confirmation"],
      8903 +         strategy_type="CRS",
      8904 +     ),
      8905 + ]
      8906 +
      8907 +
      8908 + # =============================================================================
      8909 + # SQUEEZE BLOCKS - Bollinger inside Keltner
      8910 + # =============================================================================
      8911 +
      8912 + SQUEEZE_BLOCKS = [
      8913 +     # Squeeze On (low volatility)
      8914 +     PatternBlock(
      8915 +         id="SQUEEZE_ON",
      8916 +         name="Squeeze On",
      8917 +         category="squeeze",
      8918 +         formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period}, nbdevup=2,
           +nbdevdn=2)
      8919 + df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      8920 + df['kc_upper'] = ta.EMA(df['close'], timeperiod={period}) + df['atr'] * 1.5
      8921 + df['kc_lower'] = ta.EMA(df['close'], timeperiod={period}) - df['atr'] * 1.5
      8922 + df['squeeze_on'] = (df['bb_lower'] > df['kc_lower']) & (df['bb_upper'] < df['kc_upper'])
      8923 + df['entry_signal'] = df['squeeze_on'] & ~df['squeeze_on'].shift(1)""",
      8924 +         params={"period": [20]},
      8925 +         direction="bidi",
      8926 +         lookback=30,
      8927 +         indicators=["BBANDS", "ATR", "EMA"],
      8928 +         combinable_with=["momentum", "threshold"],
      8929 +         strategy_type="SQZ",
      8930 +     ),
      8931 +     # Squeeze Fire Long
      8932 +     PatternBlock(
      8933 +         id="SQUEEZE_FIRE_LONG",
      8934 +         name="Squeeze Fire Long",
      8935 +         category="squeeze",
      8936 +         formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period}, nbdevup=2,
           +nbdevdn=2)
      8937 + df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      8938 + df['kc_upper'] = ta.EMA(df['close'], timeperiod={period}) + df['atr'] * 1.5
      8939 + df['kc_lower'] = ta.EMA(df['close'], timeperiod={period}) - df['atr'] * 1.5
      8940 + df['squeeze_on'] = (df['bb_lower'] > df['kc_lower']) & (df['bb_upper'] < df['kc_upper'])
      8941 + df['squeeze_off'] = ~df['squeeze_on'] & df['squeeze_on'].shift(1)
      8942 + df['mom'] = df['close'] - ta.SMA(df['close'], timeperiod={period})
      8943 + df['mom_up'] = df['mom'] > 0
      8944 + df['entry_signal'] = df['squeeze_off'] & df['mom_up']""",
      8945 +         params={"period": [20]},
      8946 +         direction="long",
      8947 +         lookback=35,
      8948 +         indicators=["BBANDS", "ATR", "EMA", "SMA"],
      8949 +         combinable_with=["volume", "confirmation"],
      8950 +         strategy_type="SQZ",
      8951 +     ),
      8952 +     # Squeeze Fire Short
      8953 +     PatternBlock(
      8954 +         id="SQUEEZE_FIRE_SHORT",
      8955 +         name="Squeeze Fire Short",
      8956 +         category="squeeze",
      8957 +         formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod={period}, nbdevup=2,
           +nbdevdn=2)
      8958 + df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      8959 + df['kc_upper'] = ta.EMA(df['close'], timeperiod={period}) + df['atr'] * 1.5
      8960 + df['kc_lower'] = ta.EMA(df['close'], timeperiod={period}) - df['atr'] * 1.5
      8961 + df['squeeze_on'] = (df['bb_lower'] > df['kc_lower']) & (df['bb_upper'] < df['kc_upper'])
      8962 + df['squeeze_off'] = ~df['squeeze_on'] & df['squeeze_on'].shift(1)
      8963 + df['mom'] = df['close'] - ta.SMA(df['close'], timeperiod={period})
      8964 + df['mom_down'] = df['mom'] < 0
      8965 + df['entry_signal'] = df['squeeze_off'] & df['mom_down']""",
      8966 +         params={"period": [20]},
      8967 +         direction="short",
      8968 +         lookback=35,
      8969 +         indicators=["BBANDS", "ATR", "EMA", "SMA"],
      8970 +         combinable_with=["volume", "confirmation"],
      8971 +         strategy_type="SQZ",
      8972 +     ),
      8973 + ]
      8974 +
      8975 +
      8976 + # =============================================================================
      8977 + # PRICE TRANSFORM BLOCKS
      8978 + # =============================================================================
      8979 +
      8980 + PRICE_TRANSFORM_BLOCKS = [
      8981 +     # Log Return Extreme
      8982 +     PatternBlock(
      8983 +         id="LOG_RETURN_EXTREME",
      8984 +         name="Log Return Extreme",
      8985 +         category="price_transform",
      8986 +         formula_template="""df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
      8987 + df['log_ret_std'] = df['log_ret'].rolling({period}).std()
      8988 + df['extreme_neg'] = df['log_ret'] < -df['log_ret_std'] * {mult}
      8989 + df['entry_signal'] = df['extreme_neg']""",
      8990 +         params={"period": [20], "mult": [2.0, 2.5]},
      8991 +         direction="long",
      8992 +         lookback=30,
      8993 +         indicators=[],
      8994 +         combinable_with=["volume", "confirmation"],
      8995 +         strategy_type="PTR",
      8996 +     ),
      8997 +     # Normalized Price Level
      8998 +     PatternBlock(
      8999 +         id="NORMALIZED_PRICE_LOW",
      9000 +         name="Normalized Price Low",
      9001 +         category="price_transform",
      9002 +         formula_template="""df['price_max'] = df['close'].rolling({period}).max()
      9003 + df['price_min'] = df['close'].rolling({period}).min()
      9004 + df['norm_price'] = (df['close'] - df['price_min']) / (df['price_max'] - df['price_min'] + 1e-10)
      9005 + df['low_norm'] = df['norm_price'] < {level}
      9006 + df['entry_signal'] = df['low_norm']""",
      9007 +         params={"period": [50, 100], "level": [0.1, 0.2]},
      9008 +         direction="long",
      9009 +         lookback=110,
      9010 +         indicators=[],
      9011 +         combinable_with=["momentum", "confirmation"],
      9012 +         strategy_type="PTR",
      9013 +     ),
      9014 +     # Price Z-Score Extreme
      9015 +     PatternBlock(
      9016 +         id="PRICE_ZSCORE_EXTREME",
      9017 +         name="Price Z-Score Extreme",
      9018 +         category="price_transform",
      9019 +         formula_template="""df['price_ma'] = df['close'].rolling({period}).mean()
      9020 + df['price_std'] = df['close'].rolling({period}).std()
      9021 + df['zscore'] = (df['close'] - df['price_ma']) / (df['price_std'] + 1e-10)
      9022 + df['extreme_low'] = df['zscore'] < -{threshold}
      9023 + df['entry_signal'] = df['extreme_low']""",
      9024 +         params={"period": [20, 50], "threshold": [2.0, 2.5]},
      9025 +         direction="long",
      9026 +         lookback=60,
      9027 +         indicators=[],
      9028 +         combinable_with=["volume", "confirmation"],
      9029 +         strategy_type="PTR",
      9030 +     ),
      9031 + ]
      9032 +
      9033 +
      9034 + # =============================================================================
      9035 + # ADAPTIVE CHANNEL BLOCKS
      9036 + # =============================================================================
      9037 +
      9038 + ADAPTIVE_CHANNEL_BLOCKS = [
      9039 +     # Adaptive Channel Breakout
      9040 +     PatternBlock(
      9041 +         id="ADAPTIVE_CHANNEL_BREAK_UP",
      9042 +         name="Adaptive Channel Breakout Up",
      9043 +         category="adaptive_channel",
      9044 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      9045 + df['mid'] = ta.EMA(df['close'], timeperiod={period})
      9046 + df['upper'] = df['mid'] + df['atr'] * {mult}
      9047 + df['lower'] = df['mid'] - df['atr'] * {mult}
      9048 + df['breakout'] = (df['close'] > df['upper']) & (df['close'].shift(1) <= df['upper'].shift(1))
      9049 + df['entry_signal'] = df['breakout']""",
      9050 +         params={"period": [20], "mult": [2.0, 2.5]},
      9051 +         direction="long",
      9052 +         lookback=30,
      9053 +         indicators=["ATR", "EMA"],
      9054 +         combinable_with=["volume", "momentum"],
      9055 +         strategy_type="ACH",
      9056 +     ),
      9057 +     # Adaptive Channel Bounce
      9058 +     PatternBlock(
      9059 +         id="ADAPTIVE_CHANNEL_BOUNCE",
      9060 +         name="Adaptive Channel Bounce",
      9061 +         category="adaptive_channel",
      9062 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      9063 + df['mid'] = ta.EMA(df['close'], timeperiod={period})
      9064 + df['lower'] = df['mid'] - df['atr'] * {mult}
      9065 + df['at_lower'] = df['low'] <= df['lower'] * 1.01
      9066 + df['bounce'] = df['close'] > df['open']
      9067 + df['entry_signal'] = df['at_lower'] & df['bounce']""",
      9068 +         params={"period": [20], "mult": [2.0, 2.5]},
      9069 +         direction="long",
      9070 +         lookback=30,
      9071 +         indicators=["ATR", "EMA"],
      9072 +         combinable_with=["volume", "confirmation"],
      9073 +         strategy_type="ACH",
      9074 +     ),
      9075 +     # Adaptive Channel Width Expansion
      9076 +     PatternBlock(
      9077 +         id="ADAPTIVE_CHANNEL_EXPAND",
      9078 +         name="Adaptive Channel Expansion",
      9079 +         category="adaptive_channel",
      9080 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      9081 + df['atr_ma'] = df['atr'].rolling({period}).mean()
      9082 + df['expansion'] = df['atr'] > df['atr_ma'] * {mult}
      9083 + df['uptrend'] = df['close'] > ta.EMA(df['close'], timeperiod={period})
      9084 + df['entry_signal'] = df['expansion'] & df['uptrend']""",
      9085 +         params={"period": [14], "mult": [1.3, 1.5]},
      9086 +         direction="long",
      9087 +         lookback=30,
      9088 +         indicators=["ATR", "EMA"],
      9089 +         combinable_with=["momentum", "confirmation"],
      9090 +         strategy_type="ACH",
      9091 +     ),
      9092 + ]
      9093 +
      9094 +
      9095 + # =============================================================================
      9096 + # MOMENTUM QUALITY BLOCKS
      9097 + # =============================================================================
      9098 +
      9099 + MOMENTUM_QUALITY_BLOCKS = [
      9100 +     # Smooth Momentum
      9101 +     PatternBlock(
      9102 +         id="SMOOTH_MOMENTUM",
      9103 +         name="Smooth Momentum",
      9104 +         category="momentum_quality",
      9105 +         formula_template="""df['mom'] = df['close'] - df['close'].shift({period})
      9106 + df['mom_smooth'] = ta.EMA(df['mom'], timeperiod=5)
      9107 + df['mom_diff'] = abs(df['mom'] - df['mom_smooth'])
      9108 + df['smooth_ratio'] = df['mom_diff'].rolling(10).mean() / (abs(df['mom']).rolling(10).mean() + 1e-10)
      9109 + df['is_smooth'] = df['smooth_ratio'] < {threshold}
      9110 + df['positive_mom'] = df['mom_smooth'] > 0
      9111 + df['entry_signal'] = df['is_smooth'] & df['positive_mom']""",
      9112 +         params={"period": [10, 20], "threshold": [0.3, 0.4]},
      9113 +         direction="long",
      9114 +         lookback=40,
      9115 +         indicators=["EMA"],
      9116 +         combinable_with=["volume", "confirmation"],
      9117 +         strategy_type="MQU",
      9118 +     ),
      9119 +     # Accelerating Momentum
      9120 +     PatternBlock(
      9121 +         id="ACCEL_MOMENTUM",
      9122 +         name="Accelerating Momentum",
      9123 +         category="momentum_quality",
      9124 +         formula_template="""df['mom'] = df['close'] - df['close'].shift({period})
      9125 + df['mom_accel'] = df['mom'] - df['mom'].shift(3)
      9126 + df['accel_positive'] = df['mom_accel'] > 0
      9127 + df['mom_positive'] = df['mom'] > 0
      9128 + df['increasing'] = df['mom_accel'] > df['mom_accel'].shift(1)
      9129 + df['entry_signal'] = df['accel_positive'] & df['mom_positive'] & df['increasing']""",
      9130 +         params={"period": [10, 14]},
      9131 +         direction="long",
      9132 +         lookback=30,
      9133 +         indicators=[],
      9134 +         combinable_with=["volume", "threshold"],
      9135 +         strategy_type="MQU",
      9136 +     ),
      9137 +     # Momentum Divergence Quality
      9138 +     PatternBlock(
      9139 +         id="MOM_DIVERGENCE_QUALITY",
      9140 +         name="Momentum Divergence Quality",
      9141 +         category="momentum_quality",
      9142 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
      9143 + df['price_lower'] = df['close'] < df['close'].shift(5)
      9144 + df['rsi_higher'] = df['rsi'] > df['rsi'].shift(5)
      9145 + df['divergence'] = df['price_lower'] & df['rsi_higher']
      9146 + df['rsi_recovering'] = df['rsi'] > df['rsi'].shift(1)
      9147 + df['entry_signal'] = df['divergence'] & df['rsi_recovering']""",
      9148 +         params={"period": [14]},
      9149 +         direction="long",
      9150 +         lookback=30,
      9151 +         indicators=["RSI"],
      9152 +         combinable_with=["volume", "confirmation"],
      9153 +         strategy_type="MQU",
      9154 +     ),
      9155 +     # Consistent Momentum
      9156 +     PatternBlock(
      9157 +         id="CONSISTENT_MOMENTUM",
      9158 +         name="Consistent Momentum",
      9159 +         category="momentum_quality",
      9160 +         formula_template="""df['ret'] = df['close'].pct_change()
      9161 + df['positive'] = df['ret'] > 0
      9162 + df['pos_count'] = df['positive'].rolling({period}).sum()
      9163 + df['consistency'] = df['pos_count'] / {period}
      9164 + df['high_consistency'] = df['consistency'] > {threshold}
      9165 + df['still_positive'] = df['ret'] > 0
      9166 + df['entry_signal'] = df['high_consistency'] & df['still_positive']""",
      9167 +         params={"period": [10, 20], "threshold": [0.65, 0.7]},
      9168 +         direction="long",
      9169 +         lookback=30,
      9170 +         indicators=[],
      9171 +         combinable_with=["volume", "momentum"],
      9172 +         strategy_type="MQU",
      9173 +     ),
      9174 + ]
      9175 +
      9176 +
      9177 + # =============================================================================
      9178   # ALL BLOCKS COMBINED
      9179   # =============================================================================
      9180

● Ora aggiorno ALL_BLOCKS per includere i nuovi gruppi.

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      9293       + PRICE_RATIO_BLOCKS
      9294       + STRUCTURE_BREAK_BLOCKS
      9295       + IMPULSE_CORRECTION_BLOCKS
      9296 +     + FRACTAL_BLOCKS
      9297 +     + VOLUME_PROFILE_BLOCKS
      9298 +     + ZIGZAG_BLOCKS
      9299 +     + VORTEX_BLOCKS
      9300 +     + MASS_INDEX_BLOCKS
      9301 +     + CONNORS_RSI_BLOCKS
      9302 +     + SQUEEZE_BLOCKS
      9303 +     + PRICE_TRANSFORM_BLOCKS
      9304 +     + ADAPTIVE_CHANNEL_BLOCKS
      9305 +     + MOMENTUM_QUALITY_BLOCKS
      9306   )
      9307
      9308   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python -c "
      from src.generator.pattern_gen.building_blocks import ALL_BLOCKS, BLOCKS_BY_CATEGORY…)
  ⎿  Total blocks: 478
     Categories: 123
     … +23 lines (ctrl+o to expand)

● Round 12 completato!

  Risultati:
  - Blocchi totali: 478 (da 447, +31)
  - Categorie: 123 (da 113, +10)
  - Validazione: 200/200 OK
  - Lookahead: 0 problemi
  - Strategie stimate: ~105,288

  ---
  Altre possibili migliorie (Round 13)?

  Potrei aggiungere altri ~30 blocchi:

  1. PSAR_EXTENDED_BLOCKS (3) - Parabolic SAR flip, acceleration, proximity
  2. CUMULATIVE_DELTA_BLOCKS (3) - Proxy cumulative delta via volume/price
  3. EFFICIENCY_RATIO_BLOCKS (3) - Kaufman efficiency ratio per trend quality
  4. CHOPPINESS_BLOCKS (3) - Choppiness index per sideways detection
  5. DETRENDED_PRICE_BLOCKS (3) - DPO crossovers e extremes
  6. TRUE_STRENGTH_INDEX_BLOCKS (3) - TSI crossover, extreme, divergence
  7. ULTIMATE_OSC_EXT_BLOCKS (3) - UO extreme levels e signals
  8. PRICE_ACTION_ZONES_BLOCKS (3) - Supply/demand zone detection
  9. TWIN_RANGE_BLOCKS (3) - Double range filter per direction
  10. IMPULSE_MACD_BLOCKS (3) - MACD con impulse coloring logic

  Totale: +30 blocchi → 508 blocchi, ~112,000+ strategie

  Vuoi che implementi?

✻ Worked for 2m 23s

❯ si

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 50 lines

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 60 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 619 lines
      9175
      9176
      9177   # =============================================================================
      9178 + # PSAR EXTENDED BLOCKS
      9179 + # =============================================================================
      9180 +
      9181 + PSAR_EXTENDED_BLOCKS = [
      9182 +     # PSAR Flip Long
      9183 +     PatternBlock(
      9184 +         id="PSAR_FLIP_LONG",
      9185 +         name="PSAR Flip to Long",
      9186 +         category="psar_extended",
      9187 +         formula_template="""df['sar'] = ta.SAR(df['high'], df['low'], acceleration={accel}, maximum={max_accel})
      9188 + df['sar_below'] = df['sar'] < df['close']
      9189 + df['sar_was_above'] = df['sar'].shift(1) > df['close'].shift(1)
      9190 + df['flip_long'] = df['sar_below'] & df['sar_was_above']
      9191 + df['entry_signal'] = df['flip_long']""",
      9192 +         params={"accel": [0.02], "max_accel": [0.2]},
      9193 +         direction="long",
      9194 +         lookback=20,
      9195 +         indicators=["SAR"],
      9196 +         combinable_with=["volume", "momentum", "confirmation"],
      9197 +         strategy_type="PSE",
      9198 +     ),
      9199 +     # PSAR Proximity
      9200 +     PatternBlock(
      9201 +         id="PSAR_PROXIMITY",
      9202 +         name="PSAR Proximity",
      9203 +         category="psar_extended",
      9204 +         formula_template="""df['sar'] = ta.SAR(df['high'], df['low'], acceleration={accel}, maximum={max_accel})
      9205 + df['sar_below'] = df['sar'] < df['close']
      9206 + df['distance'] = (df['close'] - df['sar']) / df['close']
      9207 + df['close_to_sar'] = df['distance'] < {proximity}
      9208 + df['uptrend'] = df['sar_below']
      9209 + df['entry_signal'] = df['close_to_sar'] & df['uptrend']""",
      9210 +         params={"accel": [0.02], "max_accel": [0.2], "proximity": [0.01, 0.015]},
      9211 +         direction="long",
      9212 +         lookback=20,
      9213 +         indicators=["SAR"],
      9214 +         combinable_with=["volume", "confirmation"],
      9215 +         strategy_type="PSE",
      9216 +     ),
      9217 +     # PSAR Acceleration Zone
      9218 +     PatternBlock(
      9219 +         id="PSAR_ACCEL_ZONE",
      9220 +         name="PSAR Acceleration Zone",
      9221 +         category="psar_extended",
      9222 +         formula_template="""df['sar'] = ta.SAR(df['high'], df['low'], acceleration={accel}, maximum={max_accel})
      9223 + df['sar_below'] = df['sar'] < df['close']
      9224 + df['sar_change'] = df['sar'] - df['sar'].shift(1)
      9225 + df['accelerating'] = df['sar_change'] > df['sar_change'].shift(1)
      9226 + df['strong_accel'] = df['accelerating'].rolling(3).sum() >= 2
      9227 + df['entry_signal'] = df['strong_accel'] & df['sar_below']""",
      9228 +         params={"accel": [0.02], "max_accel": [0.2]},
      9229 +         direction="long",
      9230 +         lookback=25,
      9231 +         indicators=["SAR"],
      9232 +         combinable_with=["momentum", "threshold"],
      9233 +         strategy_type="PSE",
      9234 +     ),
      9235 + ]
      9236 +
      9237 +
      9238 + # =============================================================================
      9239 + # CUMULATIVE DELTA BLOCKS (proxy via volume/price)
      9240 + # =============================================================================
      9241 +
      9242 + CUMULATIVE_DELTA_BLOCKS = [
      9243 +     # Volume Delta Positive
      9244 +     PatternBlock(
      9245 +         id="VOL_DELTA_POSITIVE",
      9246 +         name="Volume Delta Positive",
      9247 +         category="cumulative_delta",
      9248 +         formula_template="""df['price_up'] = df['close'] > df['open']
      9249 + df['delta'] = np.where(df['price_up'], df['volume'], -df['volume'])
      9250 + df['cum_delta'] = df['delta'].rolling({period}).sum()
      9251 + df['delta_positive'] = df['cum_delta'] > 0
      9252 + df['delta_rising'] = df['cum_delta'] > df['cum_delta'].shift(1)
      9253 + df['entry_signal'] = df['delta_positive'] & df['delta_rising']""",
      9254 +         params={"period": [10, 20]},
      9255 +         direction="long",
      9256 +         lookback=30,
      9257 +         indicators=[],
      9258 +         combinable_with=["momentum", "threshold"],
      9259 +         strategy_type="CDL",
      9260 +     ),
      9261 +     # Volume Delta Divergence
      9262 +     PatternBlock(
      9263 +         id="VOL_DELTA_DIVERGENCE",
      9264 +         name="Volume Delta Divergence",
      9265 +         category="cumulative_delta",
      9266 +         formula_template="""df['price_up'] = df['close'] > df['open']
      9267 + df['delta'] = np.where(df['price_up'], df['volume'], -df['volume'])
      9268 + df['cum_delta'] = df['delta'].rolling({period}).sum()
      9269 + df['price_down'] = df['close'] < df['close'].shift(5)
      9270 + df['delta_up'] = df['cum_delta'] > df['cum_delta'].shift(5)
      9271 + df['divergence'] = df['price_down'] & df['delta_up']
      9272 + df['entry_signal'] = df['divergence']""",
      9273 +         params={"period": [20]},
      9274 +         direction="long",
      9275 +         lookback=35,
      9276 +         indicators=[],
      9277 +         combinable_with=["confirmation", "volume"],
      9278 +         strategy_type="CDL",
      9279 +     ),
      9280 +     # Volume Delta Extreme
      9281 +     PatternBlock(
      9282 +         id="VOL_DELTA_EXTREME",
      9283 +         name="Volume Delta Extreme",
      9284 +         category="cumulative_delta",
      9285 +         formula_template="""df['price_up'] = df['close'] > df['open']
      9286 + df['delta'] = np.where(df['price_up'], df['volume'], -df['volume'])
      9287 + df['cum_delta'] = df['delta'].rolling({period}).sum()
      9288 + df['delta_ma'] = df['cum_delta'].rolling({period}).mean()
      9289 + df['delta_std'] = df['cum_delta'].rolling({period}).std()
      9290 + df['extreme_neg'] = df['cum_delta'] < df['delta_ma'] - df['delta_std'] * {mult}
      9291 + df['entry_signal'] = df['extreme_neg']""",
      9292 +         params={"period": [20], "mult": [1.5, 2.0]},
      9293 +         direction="long",
      9294 +         lookback=40,
      9295 +         indicators=[],
      9296 +         combinable_with=["momentum", "confirmation"],
      9297 +         strategy_type="CDL",
      9298 +     ),
      9299 + ]
      9300 +
      9301 +
      9302 + # =============================================================================
      9303 + # EFFICIENCY RATIO BLOCKS (Kaufman)
      9304 + # =============================================================================
      9305 +
      9306 + EFFICIENCY_RATIO_BLOCKS = [
      9307 +     # High Efficiency Ratio
      9308 +     PatternBlock(
      9309 +         id="HIGH_EFFICIENCY_RATIO",
      9310 +         name="High Efficiency Ratio",
      9311 +         category="efficiency_ratio",
      9312 +         formula_template="""df['change'] = abs(df['close'] - df['close'].shift({period}))
      9313 + df['volatility'] = abs(df['close'] - df['close'].shift(1)).rolling({period}).sum()
      9314 + df['er'] = df['change'] / (df['volatility'] + 1e-10)
      9315 + df['high_er'] = df['er'] > {threshold}
      9316 + df['uptrend'] = df['close'] > df['close'].shift({period})
      9317 + df['entry_signal'] = df['high_er'] & df['uptrend']""",
      9318 +         params={"period": [10, 20], "threshold": [0.5, 0.6]},
      9319 +         direction="long",
      9320 +         lookback=30,
      9321 +         indicators=[],
      9322 +         combinable_with=["momentum", "volume"],
      9323 +         strategy_type="EFR",
      9324 +     ),
      9325 +     # Efficiency Ratio Rising
      9326 +     PatternBlock(
      9327 +         id="ER_RISING",
      9328 +         name="Efficiency Ratio Rising",
      9329 +         category="efficiency_ratio",
      9330 +         formula_template="""df['change'] = abs(df['close'] - df['close'].shift({period}))
      9331 + df['volatility'] = abs(df['close'] - df['close'].shift(1)).rolling({period}).sum()
      9332 + df['er'] = df['change'] / (df['volatility'] + 1e-10)
      9333 + df['er_rising'] = df['er'] > df['er'].shift(3)
      9334 + df['er_above_mid'] = df['er'] > 0.3
      9335 + df['entry_signal'] = df['er_rising'] & df['er_above_mid']""",
      9336 +         params={"period": [10, 14]},
      9337 +         direction="bidi",
      9338 +         lookback=25,
      9339 +         indicators=[],
      9340 +         combinable_with=["momentum", "threshold"],
      9341 +         strategy_type="EFR",
      9342 +     ),
      9343 +     # Low Efficiency (Choppy) to High
      9344 +     PatternBlock(
      9345 +         id="ER_LOW_TO_HIGH",
      9346 +         name="Efficiency Low to High",
      9347 +         category="efficiency_ratio",
      9348 +         formula_template="""df['change'] = abs(df['close'] - df['close'].shift({period}))
      9349 + df['volatility'] = abs(df['close'] - df['close'].shift(1)).rolling({period}).sum()
      9350 + df['er'] = df['change'] / (df['volatility'] + 1e-10)
      9351 + df['was_low'] = df['er'].shift(3) < {low_thresh}
      9352 + df['now_high'] = df['er'] > {high_thresh}
      9353 + df['entry_signal'] = df['was_low'] & df['now_high']""",
      9354 +         params={"period": [10], "low_thresh": [0.2], "high_thresh": [0.4, 0.5]},
      9355 +         direction="bidi",
      9356 +         lookback=25,
      9357 +         indicators=[],
      9358 +         combinable_with=["momentum", "confirmation"],
      9359 +         strategy_type="EFR",
      9360 +     ),
      9361 + ]
      9362 +
      9363 +
      9364 + # =============================================================================
      9365 + # CHOPPINESS BLOCKS
      9366 + # =============================================================================
      9367 +
      9368 + CHOPPINESS_BLOCKS = [
      9369 +     # Low Choppiness (Trending)
      9370 +     PatternBlock(
      9371 +         id="LOW_CHOPPINESS",
      9372 +         name="Low Choppiness Trending",
      9373 +         category="choppiness",
      9374 +         formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)),
           +abs(df['low'] - df['close'].shift(1))))
      9375 + df['atr_sum'] = df['tr'].rolling({period}).sum()
      9376 + df['high_low_range'] = df['high'].rolling({period}).max() - df['low'].rolling({period}).min()
      9377 + df['chop'] = 100 * np.log10(df['atr_sum'] / (df['high_low_range'] + 1e-10)) / np.log10({period})
      9378 + df['low_chop'] = df['chop'] < {threshold}
      9379 + df['uptrend'] = df['close'] > df['close'].shift(5)
      9380 + df['entry_signal'] = df['low_chop'] & df['uptrend']""",
      9381 +         params={"period": [14], "threshold": [38.2, 40]},
      9382 +         direction="long",
      9383 +         lookback=25,
      9384 +         indicators=[],
      9385 +         combinable_with=["momentum", "threshold"],
      9386 +         strategy_type="CHP",
      9387 +     ),
      9388 +     # High Choppiness Breaking Out
      9389 +     PatternBlock(
      9390 +         id="CHOP_BREAKOUT",
      9391 +         name="Choppiness Breakout",
      9392 +         category="choppiness",
      9393 +         formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)),
           +abs(df['low'] - df['close'].shift(1))))
      9394 + df['atr_sum'] = df['tr'].rolling({period}).sum()
      9395 + df['high_low_range'] = df['high'].rolling({period}).max() - df['low'].rolling({period}).min()
      9396 + df['chop'] = 100 * np.log10(df['atr_sum'] / (df['high_low_range'] + 1e-10)) / np.log10({period})
      9397 + df['was_high'] = df['chop'].shift(1) > {high_thresh}
      9398 + df['now_low'] = df['chop'] < {low_thresh}
      9399 + df['entry_signal'] = df['was_high'] & df['now_low']""",
      9400 +         params={"period": [14], "high_thresh": [55, 60], "low_thresh": [45, 50]},
      9401 +         direction="bidi",
      9402 +         lookback=25,
      9403 +         indicators=[],
      9404 +         combinable_with=["volume", "confirmation"],
      9405 +         strategy_type="CHP",
      9406 +     ),
      9407 +     # Choppiness Extreme
      9408 +     PatternBlock(
      9409 +         id="CHOP_EXTREME",
      9410 +         name="Choppiness Extreme Sideways",
      9411 +         category="choppiness",
      9412 +         formula_template="""df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)),
           +abs(df['low'] - df['close'].shift(1))))
      9413 + df['atr_sum'] = df['tr'].rolling({period}).sum()
      9414 + df['high_low_range'] = df['high'].rolling({period}).max() - df['low'].rolling({period}).min()
      9415 + df['chop'] = 100 * np.log10(df['atr_sum'] / (df['high_low_range'] + 1e-10)) / np.log10({period})
      9416 + df['extreme_chop'] = df['chop'] > {threshold}
      9417 + df['extreme_days'] = df['extreme_chop'].rolling(5).sum() >= 3
      9418 + df['entry_signal'] = df['extreme_days']""",
      9419 +         params={"period": [14], "threshold": [61.8, 65]},
      9420 +         direction="bidi",
      9421 +         lookback=30,
      9422 +         indicators=[],
      9423 +         combinable_with=["volume", "momentum"],
      9424 +         strategy_type="CHP",
      9425 +     ),
      9426 + ]
      9427 +
      9428 +
      9429 + # =============================================================================
      9430 + # DETRENDED PRICE BLOCKS
      9431 + # =============================================================================
      9432 +
      9433 + DETRENDED_PRICE_BLOCKS = [
      9434 +     # DPO Oversold
      9435 +     PatternBlock(
      9436 +         id="DPO_OVERSOLD",
      9437 +         name="DPO Oversold",
      9438 +         category="detrended_price",
      9439 +         formula_template="""df['dpo_period'] = {period} // 2 + 1
      9440 + df['sma'] = ta.SMA(df['close'], timeperiod={period})
      9441 + df['dpo'] = df['close'].shift(df['dpo_period'].iloc[0]) - df['sma']
      9442 + df['dpo_std'] = df['dpo'].rolling({period}).std()
      9443 + df['oversold'] = df['dpo'] < -df['dpo_std'] * {mult}
      9444 + df['entry_signal'] = df['oversold']""",
      9445 +         params={"period": [20], "mult": [1.5, 2.0]},
      9446 +         direction="long",
      9447 +         lookback=40,
      9448 +         indicators=["SMA"],
      9449 +         combinable_with=["volume", "confirmation"],
      9450 +         strategy_type="DTP",
      9451 +     ),
      9452 +     # DPO Zero Cross Up
      9453 +     PatternBlock(
      9454 +         id="DPO_CROSS_UP",
      9455 +         name="DPO Cross Up",
      9456 +         category="detrended_price",
      9457 +         formula_template="""df['dpo_period'] = {period} // 2 + 1
      9458 + df['sma'] = ta.SMA(df['close'], timeperiod={period})
      9459 + df['dpo'] = df['close'].shift(df['dpo_period'].iloc[0]) - df['sma']
      9460 + df['cross_up'] = (df['dpo'] > 0) & (df['dpo'].shift(1) <= 0)
      9461 + df['entry_signal'] = df['cross_up']""",
      9462 +         params={"period": [20, 30]},
      9463 +         direction="long",
      9464 +         lookback=45,
      9465 +         indicators=["SMA"],
      9466 +         combinable_with=["momentum", "threshold"],
      9467 +         strategy_type="DTP",
      9468 +     ),
      9469 +     # DPO Positive Momentum
      9470 +     PatternBlock(
      9471 +         id="DPO_POSITIVE_MOM",
      9472 +         name="DPO Positive Momentum",
      9473 +         category="detrended_price",
      9474 +         formula_template="""df['dpo_period'] = {period} // 2 + 1
      9475 + df['sma'] = ta.SMA(df['close'], timeperiod={period})
      9476 + df['dpo'] = df['close'].shift(df['dpo_period'].iloc[0]) - df['sma']
      9477 + df['dpo_positive'] = df['dpo'] > 0
      9478 + df['dpo_rising'] = df['dpo'] > df['dpo'].shift(3)
      9479 + df['entry_signal'] = df['dpo_positive'] & df['dpo_rising']""",
      9480 +         params={"period": [20]},
      9481 +         direction="long",
      9482 +         lookback=40,
      9483 +         indicators=["SMA"],
      9484 +         combinable_with=["volume", "confirmation"],
      9485 +         strategy_type="DTP",
      9486 +     ),
      9487 + ]
      9488 +
      9489 +
      9490 + # =============================================================================
      9491 + # TRUE STRENGTH INDEX BLOCKS
      9492 + # =============================================================================
      9493 +
      9494 + TRUE_STRENGTH_INDEX_BLOCKS = [
      9495 +     # TSI Oversold
      9496 +     PatternBlock(
      9497 +         id="TSI_OVERSOLD",
      9498 +         name="TSI Oversold",
      9499 +         category="true_strength_index",
      9500 +         formula_template="""df['pc'] = df['close'] - df['close'].shift(1)
      9501 + df['pc_ds'] = ta.EMA(ta.EMA(df['pc'], timeperiod={long_period}), timeperiod={short_period})
      9502 + df['apc'] = abs(df['pc'])
      9503 + df['apc_ds'] = ta.EMA(ta.EMA(df['apc'], timeperiod={long_period}), timeperiod={short_period})
      9504 + df['tsi'] = 100 * df['pc_ds'] / (df['apc_ds'] + 1e-10)
      9505 + df['oversold'] = df['tsi'] < {level}
      9506 + df['entry_signal'] = df['oversold']""",
      9507 +         params={"long_period": [25], "short_period": [13], "level": [-25, -30]},
      9508 +         direction="long",
      9509 +         lookback=50,
      9510 +         indicators=["EMA"],
      9511 +         combinable_with=["volume", "confirmation"],
      9512 +         strategy_type="TSX",
      9513 +     ),
      9514 +     # TSI Signal Cross
      9515 +     PatternBlock(
      9516 +         id="TSI_SIGNAL_CROSS",
      9517 +         name="TSI Signal Cross Up",
      9518 +         category="true_strength_index",
      9519 +         formula_template="""df['pc'] = df['close'] - df['close'].shift(1)
      9520 + df['pc_ds'] = ta.EMA(ta.EMA(df['pc'], timeperiod={long_period}), timeperiod={short_period})
      9521 + df['apc'] = abs(df['pc'])
      9522 + df['apc_ds'] = ta.EMA(ta.EMA(df['apc'], timeperiod={long_period}), timeperiod={short_period})
      9523 + df['tsi'] = 100 * df['pc_ds'] / (df['apc_ds'] + 1e-10)
      9524 + df['signal'] = ta.EMA(df['tsi'], timeperiod=7)
      9525 + df['cross_up'] = (df['tsi'] > df['signal']) & (df['tsi'].shift(1) <= df['signal'].shift(1))
      9526 + df['entry_signal'] = df['cross_up']""",
      9527 +         params={"long_period": [25], "short_period": [13]},
      9528 +         direction="long",
      9529 +         lookback=50,
      9530 +         indicators=["EMA"],
      9531 +         combinable_with=["momentum", "threshold"],
      9532 +         strategy_type="TSX",
      9533 +     ),
      9534 +     # TSI Zero Cross
      9535 +     PatternBlock(
      9536 +         id="TSI_ZERO_CROSS",
      9537 +         name="TSI Zero Cross Up",
      9538 +         category="true_strength_index",
      9539 +         formula_template="""df['pc'] = df['close'] - df['close'].shift(1)
      9540 + df['pc_ds'] = ta.EMA(ta.EMA(df['pc'], timeperiod={long_period}), timeperiod={short_period})
      9541 + df['apc'] = abs(df['pc'])
      9542 + df['apc_ds'] = ta.EMA(ta.EMA(df['apc'], timeperiod={long_period}), timeperiod={short_period})
      9543 + df['tsi'] = 100 * df['pc_ds'] / (df['apc_ds'] + 1e-10)
      9544 + df['cross_zero'] = (df['tsi'] > 0) & (df['tsi'].shift(1) <= 0)
      9545 + df['entry_signal'] = df['cross_zero']""",
      9546 +         params={"long_period": [25], "short_period": [13]},
      9547 +         direction="long",
      9548 +         lookback=50,
      9549 +         indicators=["EMA"],
      9550 +         combinable_with=["volume", "confirmation"],
      9551 +         strategy_type="TSX",
      9552 +     ),
      9553 + ]
      9554 +
      9555 +
      9556 + # =============================================================================
      9557 + # ULTIMATE OSCILLATOR EXTENDED BLOCKS
      9558 + # =============================================================================
      9559 +
      9560 + ULTIMATE_OSC_EXT_BLOCKS = [
      9561 +     # UO Oversold Reversal
      9562 +     PatternBlock(
      9563 +         id="UO_OVERSOLD_REV",
      9564 +         name="UO Oversold Reversal",
      9565 +         category="ultimate_osc_ext",
      9566 +         formula_template="""df['uo'] = ta.ULTOSC(df['high'], df['low'], df['close'], timeperiod1=7, timeperiod2=14, timeperiod3=28)
      9567 + df['oversold'] = df['uo'] < {level}
      9568 + df['turning'] = df['uo'] > df['uo'].shift(1)
      9569 + df['entry_signal'] = df['oversold'] & df['turning']""",
      9570 +         params={"level": [30, 35]},
      9571 +         direction="long",
      9572 +         lookback=40,
      9573 +         indicators=["ULTOSC"],
      9574 +         combinable_with=["volume", "confirmation"],
      9575 +         strategy_type="UOE",
      9576 +     ),
      9577 +     # UO Bullish Divergence
      9578 +     PatternBlock(
      9579 +         id="UO_BULL_DIV",
      9580 +         name="UO Bullish Divergence",
      9581 +         category="ultimate_osc_ext",
      9582 +         formula_template="""df['uo'] = ta.ULTOSC(df['high'], df['low'], df['close'], timeperiod1=7, timeperiod2=14, timeperiod3=28)
      9583 + df['price_lower'] = df['close'] < df['close'].shift({lookback})
      9584 + df['uo_higher'] = df['uo'] > df['uo'].shift({lookback})
      9585 + df['uo_oversold'] = df['uo'] < 50
      9586 + df['divergence'] = df['price_lower'] & df['uo_higher'] & df['uo_oversold']
      9587 + df['entry_signal'] = df['divergence']""",
      9588 +         params={"lookback": [5, 10]},
      9589 +         direction="long",
      9590 +         lookback=50,
      9591 +         indicators=["ULTOSC"],
      9592 +         combinable_with=["confirmation", "momentum"],
      9593 +         strategy_type="UOE",
      9594 +     ),
      9595 +     # UO Momentum Thrust
      9596 +     PatternBlock(
      9597 +         id="UO_THRUST",
      9598 +         name="UO Momentum Thrust",
      9599 +         category="ultimate_osc_ext",
      9600 +         formula_template="""df['uo'] = ta.ULTOSC(df['high'], df['low'], df['close'], timeperiod1=7, timeperiod2=14, timeperiod3=28)
      9601 + df['uo_rise'] = df['uo'] - df['uo'].shift(3)
      9602 + df['strong_rise'] = df['uo_rise'] > {threshold}
      9603 + df['above_mid'] = df['uo'] > 50
      9604 + df['entry_signal'] = df['strong_rise'] & df['above_mid']""",
      9605 +         params={"threshold": [10, 15]},
      9606 +         direction="long",
      9607 +         lookback=40,
      9608 +         indicators=["ULTOSC"],
      9609 +         combinable_with=["volume", "threshold"],
      9610 +         strategy_type="UOE",
      9611 +     ),
      9612 + ]
      9613 +
      9614 +
      9615 + # =============================================================================
      9616 + # PRICE ACTION ZONES BLOCKS
      9617 + # =============================================================================
      9618 +
      9619 + PRICE_ACTION_ZONES_BLOCKS = [
      9620 +     # Demand Zone Touch
      9621 +     PatternBlock(
      9622 +         id="DEMAND_ZONE_TOUCH",
      9623 +         name="Demand Zone Touch",
      9624 +         category="price_action_zones",
      9625 +         formula_template="""df['swing_low'] = df['low'].rolling({period}).min()
      9626 + df['zone_top'] = df['swing_low'] * (1 + {zone_width})
      9627 + df['in_zone'] = (df['low'] <= df['zone_top']) & (df['low'] >= df['swing_low'] * 0.99)
      9628 + df['bounce'] = df['close'] > df['open']
      9629 + df['entry_signal'] = df['in_zone'] & df['bounce']""",
      9630 +         params={"period": [20, 30], "zone_width": [0.01, 0.015]},
      9631 +         direction="long",
      9632 +         lookback=40,
      9633 +         indicators=[],
      9634 +         combinable_with=["volume", "confirmation"],
      9635 +         strategy_type="PAZ",
      9636 +     ),
      9637 +     # Supply Zone Touch
      9638 +     PatternBlock(
      9639 +         id="SUPPLY_ZONE_TOUCH",
      9640 +         name="Supply Zone Touch",
      9641 +         category="price_action_zones",
      9642 +         formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
      9643 + df['zone_bottom'] = df['swing_high'] * (1 - {zone_width})
      9644 + df['in_zone'] = (df['high'] >= df['zone_bottom']) & (df['high'] <= df['swing_high'] * 1.01)
      9645 + df['rejection'] = df['close'] < df['open']
      9646 + df['entry_signal'] = df['in_zone'] & df['rejection']""",
      9647 +         params={"period": [20, 30], "zone_width": [0.01, 0.015]},
      9648 +         direction="short",
      9649 +         lookback=40,
      9650 +         indicators=[],
      9651 +         combinable_with=["volume", "confirmation"],
      9652 +         strategy_type="PAZ",
      9653 +     ),
      9654 +     # Fresh Zone Break
      9655 +     PatternBlock(
      9656 +         id="FRESH_ZONE_BREAK",
      9657 +         name="Fresh Zone Break",
      9658 +         category="price_action_zones",
      9659 +         formula_template="""df['prev_high'] = df['high'].rolling({period}).max().shift(1)
      9660 + df['breakout'] = df['close'] > df['prev_high']
      9661 + df['strong'] = df['close'] > df['prev_high'] * (1 + {margin})
      9662 + df['entry_signal'] = df['strong']""",
      9663 +         params={"period": [20], "margin": [0.002, 0.005]},
      9664 +         direction="long",
      9665 +         lookback=30,
      9666 +         indicators=[],
      9667 +         combinable_with=["volume", "momentum"],
      9668 +         strategy_type="PAZ",
      9669 +     ),
      9670 + ]
      9671 +
      9672 +
      9673 + # =============================================================================
      9674 + # TWIN RANGE BLOCKS
      9675 + # =============================================================================
      9676 +
      9677 + TWIN_RANGE_BLOCKS = [
      9678 +     # Twin Range Filter Long
      9679 +     PatternBlock(
      9680 +         id="TWIN_RANGE_LONG",
      9681 +         name="Twin Range Filter Long",
      9682 +         category="twin_range",
      9683 +         formula_template="""df['atr_fast'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={fast_period})
      9684 + df['atr_slow'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={slow_period})
      9685 + df['range_val'] = (df['atr_fast'] * {fast_mult} + df['atr_slow'] * {slow_mult}) / 2
      9686 + df['smooth_range'] = ta.EMA(df['range_val'], timeperiod=10)
      9687 + df['up'] = df['close'] > df['close'].shift(1) + df['smooth_range'].shift(1)
      9688 + df['entry_signal'] = df['up']""",
      9689 +         params={"fast_period": [5], "slow_period": [20], "fast_mult": [1.0], "slow_mult": [1.0]},
      9690 +         direction="long",
      9691 +         lookback=30,
      9692 +         indicators=["ATR", "EMA"],
      9693 +         combinable_with=["momentum", "volume"],
      9694 +         strategy_type="TWR",
      9695 +     ),
      9696 +     # Twin Range Filter Short
      9697 +     PatternBlock(
      9698 +         id="TWIN_RANGE_SHORT",
      9699 +         name="Twin Range Filter Short",
      9700 +         category="twin_range",
      9701 +         formula_template="""df['atr_fast'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={fast_period})
      9702 + df['atr_slow'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={slow_period})
      9703 + df['range_val'] = (df['atr_fast'] * {fast_mult} + df['atr_slow'] * {slow_mult}) / 2
      9704 + df['smooth_range'] = ta.EMA(df['range_val'], timeperiod=10)
      9705 + df['down'] = df['close'] < df['close'].shift(1) - df['smooth_range'].shift(1)
      9706 + df['entry_signal'] = df['down']""",
      9707 +         params={"fast_period": [5], "slow_period": [20], "fast_mult": [1.0], "slow_mult": [1.0]},
      9708 +         direction="short",
      9709 +         lookback=30,
      9710 +         indicators=["ATR", "EMA"],
      9711 +         combinable_with=["momentum", "volume"],
      9712 +         strategy_type="TWR",
      9713 +     ),
      9714 +     # Twin Range Squeeze
      9715 +     PatternBlock(
      9716 +         id="TWIN_RANGE_SQUEEZE",
      9717 +         name="Twin Range Squeeze",
      9718 +         category="twin_range",
      9719 +         formula_template="""df['atr_fast'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={fast_period})
      9720 + df['atr_slow'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={slow_period})
      9721 + df['ratio'] = df['atr_fast'] / (df['atr_slow'] + 1e-10)
      9722 + df['squeeze'] = df['ratio'] < {threshold}
      9723 + df['squeeze_days'] = df['squeeze'].rolling(5).sum() >= 3
      9724 + df['entry_signal'] = df['squeeze_days']""",
      9725 +         params={"fast_period": [5], "slow_period": [20], "threshold": [0.6, 0.7]},
      9726 +         direction="bidi",
      9727 +         lookback=30,
      9728 +         indicators=["ATR"],
      9729 +         combinable_with=["momentum", "confirmation"],
      9730 +         strategy_type="TWR",
      9731 +     ),
      9732 + ]
      9733 +
      9734 +
      9735 + # =============================================================================
      9736 + # IMPULSE MACD BLOCKS
      9737 + # =============================================================================
      9738 +
      9739 + IMPULSE_MACD_BLOCKS = [
      9740 +     # Impulse MACD Green
      9741 +     PatternBlock(
      9742 +         id="IMPULSE_MACD_GREEN",
      9743 +         name="Impulse MACD Green",
      9744 +         category="impulse_macd",
      9745 +         formula_template="""df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow},
           +signalperiod=9)
      9746 + df['hist_rising'] = df['hist'] > df['hist'].shift(1)
      9747 + df['macd_rising'] = df['macd'] > df['macd'].shift(1)
      9748 + df['green_bar'] = df['hist_rising'] & df['macd_rising']
      9749 + df['entry_signal'] = df['green_bar']""",
      9750 +         params={"fast": [12], "slow": [26]},
      9751 +         direction="long",
      9752 +         lookback=40,
      9753 +         indicators=["MACD"],
      9754 +         combinable_with=["volume", "threshold"],
      9755 +         strategy_type="IMC",
      9756 +     ),
      9757 +     # Impulse MACD Red
      9758 +     PatternBlock(
      9759 +         id="IMPULSE_MACD_RED",
      9760 +         name="Impulse MACD Red",
      9761 +         category="impulse_macd",
      9762 +         formula_template="""df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow},
           +signalperiod=9)
      9763 + df['hist_falling'] = df['hist'] < df['hist'].shift(1)
      9764 + df['macd_falling'] = df['macd'] < df['macd'].shift(1)
      9765 + df['red_bar'] = df['hist_falling'] & df['macd_falling']
      9766 + df['entry_signal'] = df['red_bar']""",
      9767 +         params={"fast": [12], "slow": [26]},
      9768 +         direction="short",
      9769 +         lookback=40,
      9770 +         indicators=["MACD"],
      9771 +         combinable_with=["volume", "threshold"],
      9772 +         strategy_type="IMC",
      9773 +     ),
      9774 +     # Impulse MACD Color Change
      9775 +     PatternBlock(
      9776 +         id="IMPULSE_MACD_CHANGE",
      9777 +         name="Impulse MACD Color Change",
      9778 +         category="impulse_macd",
      9779 +         formula_template="""df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow},
           +signalperiod=9)
      9780 + df['hist_rising'] = df['hist'] > df['hist'].shift(1)
      9781 + df['macd_rising'] = df['macd'] > df['macd'].shift(1)
      9782 + df['green'] = df['hist_rising'] & df['macd_rising']
      9783 + df['was_not_green'] = ~(df['hist'].shift(1) > df['hist'].shift(2)) | ~(df['macd'].shift(1) > df['macd'].shift(2))
      9784 + df['color_change'] = df['green'] & df['was_not_green']
      9785 + df['entry_signal'] = df['color_change']""",
      9786 +         params={"fast": [12], "slow": [26]},
      9787 +         direction="long",
      9788 +         lookback=40,
      9789 +         indicators=["MACD"],
      9790 +         combinable_with=["volume", "confirmation"],
      9791 +         strategy_type="IMC",
      9792 +     ),
      9793 + ]
      9794 +
      9795 +
      9796 + # =============================================================================
      9797   # ALL BLOCKS COMBINED
      9798   # =============================================================================
      9799

● Ora aggiorno ALL_BLOCKS.

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      9922       + PRICE_TRANSFORM_BLOCKS
      9923       + ADAPTIVE_CHANNEL_BLOCKS
      9924       + MOMENTUM_QUALITY_BLOCKS
      9925 +     + PSAR_EXTENDED_BLOCKS
      9926 +     + CUMULATIVE_DELTA_BLOCKS
      9927 +     + EFFICIENCY_RATIO_BLOCKS
      9928 +     + CHOPPINESS_BLOCKS
      9929 +     + DETRENDED_PRICE_BLOCKS
      9930 +     + TRUE_STRENGTH_INDEX_BLOCKS
      9931 +     + ULTIMATE_OSC_EXT_BLOCKS
      9932 +     + PRICE_ACTION_ZONES_BLOCKS
      9933 +     + TWIN_RANGE_BLOCKS
      9934 +     + IMPULSE_MACD_BLOCKS
      9935   )
      9936
      9937   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python -c "
      from src.generator.pattern_gen.building_blocks import ALL_BLOCKS, BLOCKS_BY_CATEGORY…)
  ⎿  Total blocks: 508
     Categories: 133
     … +23 lines (ctrl+o to expand)

● Round 13 completato!

  Risultati:
  - Blocchi totali: 508 (da 478, +30)
  - Categorie: 133 (da 123, +10)
  - Validazione: 200/200 OK
  - Lookahead: 0 problemi
  - Strategie stimate: ~109,672

  ---
  Altre possibili migliorie (Round 14)?

  Potrei aggiungere altri ~30 blocchi:

  1. WAVETREND_BLOCKS (3) - WaveTrend oscillator, overbought/oversold
  2. QQE_BLOCKS (3) - Qualitative Quantitative Estimation signals
  3. SCHAFF_TREND_BLOCKS (3) - Schaff Trend Cycle indicator
  4. FISHER_TRANSFORM_BLOCKS (3) - Fisher Transform extreme/crossover
  5. EHLERS_BLOCKS (3) - Ehlers filters (super smoother, etc.)
  6. CENTER_OF_GRAVITY_BLOCKS (3) - COG oscillator signals
  7. RELATIVE_VIGOR_BLOCKS (3) - RVI crossover e signals
  8. RAINBOW_MA_BLOCKS (3) - Rainbow moving average bands
  9. TREND_INTENSITY_BLOCKS (3) - Trend intensity index
  10. PRICE_ZONE_OSC_BLOCKS (3) - PZO extreme levels

  Totale: +30 blocchi → 538 blocchi, ~117,000+ strategie

  Vuoi che implementi?

✻ Worked for 2m 17s

❯ si

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 60 lines

● Search(pattern: "IMPULSE_MACD_BLOCKS\s*\]", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 0 lines

● Search(pattern: "IMPULSE_MACD_BLOCKS =", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 50 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 668 lines
       9794
       9795
       9796   # =============================================================================
       9797 + # WAVETREND BLOCKS
       9798 + # =============================================================================
       9799 +
       9800 + WAVETREND_BLOCKS = [
       9801 +     # WaveTrend Oversold
       9802 +     PatternBlock(
       9803 +         id="WAVETREND_OVERSOLD",
       9804 +         name="WaveTrend Oversold",
       9805 +         category="wavetrend",
       9806 +         formula_template="""df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
       9807 + df['esa'] = ta.EMA(df['hlc3'], timeperiod={period})
       9808 + df['d'] = ta.EMA(abs(df['hlc3'] - df['esa']), timeperiod={period})
       9809 + df['ci'] = (df['hlc3'] - df['esa']) / (0.015 * df['d'] + 1e-10)
       9810 + df['wt1'] = ta.EMA(df['ci'], timeperiod=21)
       9811 + df['wt2'] = ta.SMA(df['wt1'], timeperiod=4)
       9812 + df['oversold'] = df['wt1'] < {level}
       9813 + df['entry_signal'] = df['oversold']""",
       9814 +         params={"period": [10], "level": [-60, -70]},
       9815 +         direction="long",
       9816 +         lookback=40,
       9817 +         indicators=["EMA", "SMA"],
       9818 +         combinable_with=["volume", "confirmation"],
       9819 +         strategy_type="WVT",
       9820 +     ),
       9821 +     # WaveTrend Cross Up
       9822 +     PatternBlock(
       9823 +         id="WAVETREND_CROSS_UP",
       9824 +         name="WaveTrend Cross Up",
       9825 +         category="wavetrend",
       9826 +         formula_template="""df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
       9827 + df['esa'] = ta.EMA(df['hlc3'], timeperiod={period})
       9828 + df['d'] = ta.EMA(abs(df['hlc3'] - df['esa']), timeperiod={period})
       9829 + df['ci'] = (df['hlc3'] - df['esa']) / (0.015 * df['d'] + 1e-10)
       9830 + df['wt1'] = ta.EMA(df['ci'], timeperiod=21)
       9831 + df['wt2'] = ta.SMA(df['wt1'], timeperiod=4)
       9832 + df['cross_up'] = (df['wt1'] > df['wt2']) & (df['wt1'].shift(1) <= df['wt2'].shift(1))
       9833 + df['entry_signal'] = df['cross_up']""",
       9834 +         params={"period": [10]},
       9835 +         direction="long",
       9836 +         lookback=40,
       9837 +         indicators=["EMA", "SMA"],
       9838 +         combinable_with=["momentum", "threshold"],
       9839 +         strategy_type="WVT",
       9840 +     ),
       9841 +     # WaveTrend Divergence
       9842 +     PatternBlock(
       9843 +         id="WAVETREND_DIVERGENCE",
       9844 +         name="WaveTrend Divergence",
       9845 +         category="wavetrend",
       9846 +         formula_template="""df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
       9847 + df['esa'] = ta.EMA(df['hlc3'], timeperiod={period})
       9848 + df['d'] = ta.EMA(abs(df['hlc3'] - df['esa']), timeperiod={period})
       9849 + df['ci'] = (df['hlc3'] - df['esa']) / (0.015 * df['d'] + 1e-10)
       9850 + df['wt1'] = ta.EMA(df['ci'], timeperiod=21)
       9851 + df['price_lower'] = df['close'] < df['close'].shift(5)
       9852 + df['wt_higher'] = df['wt1'] > df['wt1'].shift(5)
       9853 + df['divergence'] = df['price_lower'] & df['wt_higher']
       9854 + df['entry_signal'] = df['divergence']""",
       9855 +         params={"period": [10]},
       9856 +         direction="long",
       9857 +         lookback=40,
       9858 +         indicators=["EMA"],
       9859 +         combinable_with=["volume", "confirmation"],
       9860 +         strategy_type="WVT",
       9861 +     ),
       9862 + ]
       9863 +
       9864 +
       9865 + # =============================================================================
       9866 + # QQE BLOCKS (Qualitative Quantitative Estimation)
       9867 + # =============================================================================
       9868 +
       9869 + QQE_BLOCKS = [
       9870 +     # QQE Cross Up
       9871 +     PatternBlock(
       9872 +         id="QQE_CROSS_UP",
       9873 +         name="QQE Cross Up",
       9874 +         category="qqe",
       9875 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={rsi_period})
       9876 + df['rsi_ma'] = ta.EMA(df['rsi'], timeperiod=5)
       9877 + df['atr_rsi'] = abs(df['rsi_ma'] - df['rsi_ma'].shift(1))
       9878 + df['atr_rsi_ma'] = ta.EMA(df['atr_rsi'], timeperiod={period}) * {mult}
       9879 + df['long_band'] = df['rsi_ma'] - df['atr_rsi_ma']
       9880 + df['cross_up'] = (df['rsi_ma'] > df['long_band']) & (df['rsi_ma'].shift(1) <= df['long_band'].shift(1))
       9881 + df['entry_signal'] = df['cross_up']""",
       9882 +         params={"rsi_period": [14], "period": [5], "mult": [4.236]},
       9883 +         direction="long",
       9884 +         lookback=30,
       9885 +         indicators=["RSI", "EMA"],
       9886 +         combinable_with=["volume", "momentum"],
       9887 +         strategy_type="QQE",
       9888 +     ),
       9889 +     # QQE Trend
       9890 +     PatternBlock(
       9891 +         id="QQE_TREND",
       9892 +         name="QQE Trend Mode",
       9893 +         category="qqe",
       9894 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={rsi_period})
       9895 + df['rsi_ma'] = ta.EMA(df['rsi'], timeperiod=5)
       9896 + df['atr_rsi'] = abs(df['rsi_ma'] - df['rsi_ma'].shift(1))
       9897 + df['atr_rsi_ma'] = ta.EMA(df['atr_rsi'], timeperiod={period}) * {mult}
       9898 + df['trend_up'] = df['rsi_ma'] > 50
       9899 + df['strong'] = df['rsi_ma'] > (50 + df['atr_rsi_ma'])
       9900 + df['entry_signal'] = df['trend_up'] & df['strong']""",
       9901 +         params={"rsi_period": [14], "period": [5], "mult": [4.236]},
       9902 +         direction="long",
       9903 +         lookback=30,
       9904 +         indicators=["RSI", "EMA"],
       9905 +         combinable_with=["threshold", "confirmation"],
       9906 +         strategy_type="QQE",
       9907 +     ),
       9908 +     # QQE Zero Cross
       9909 +     PatternBlock(
       9910 +         id="QQE_ZERO_CROSS",
       9911 +         name="QQE Zero Cross",
       9912 +         category="qqe",
       9913 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={rsi_period})
       9914 + df['rsi_ma'] = ta.EMA(df['rsi'], timeperiod=5)
       9915 + df['rsi_centered'] = df['rsi_ma'] - 50
       9916 + df['cross_zero'] = (df['rsi_centered'] > 0) & (df['rsi_centered'].shift(1) <= 0)
       9917 + df['entry_signal'] = df['cross_zero']""",
       9918 +         params={"rsi_period": [14]},
       9919 +         direction="long",
       9920 +         lookback=25,
       9921 +         indicators=["RSI", "EMA"],
       9922 +         combinable_with=["volume", "confirmation"],
       9923 +         strategy_type="QQE",
       9924 +     ),
       9925 + ]
       9926 +
       9927 +
       9928 + # =============================================================================
       9929 + # SCHAFF TREND CYCLE BLOCKS
       9930 + # =============================================================================
       9931 +
       9932 + SCHAFF_TREND_BLOCKS = [
       9933 +     # STC Oversold
       9934 +     PatternBlock(
       9935 +         id="STC_OVERSOLD",
       9936 +         name="STC Oversold",
       9937 +         category="schaff_trend",
       9938 +         formula_template="""df['macd'], _, _ = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod=9)
       9939 + df['macd_min'] = df['macd'].rolling({cycle}).min()
       9940 + df['macd_max'] = df['macd'].rolling({cycle}).max()
       9941 + df['stoch_macd'] = (df['macd'] - df['macd_min']) / (df['macd_max'] - df['macd_min'] + 1e-10) * 100
       9942 + df['stc1'] = ta.EMA(df['stoch_macd'], timeperiod=3)
       9943 + df['stc1_min'] = df['stc1'].rolling({cycle}).min()
       9944 + df['stc1_max'] = df['stc1'].rolling({cycle}).max()
       9945 + df['stc'] = (df['stc1'] - df['stc1_min']) / (df['stc1_max'] - df['stc1_min'] + 1e-10) * 100
       9946 + df['oversold'] = df['stc'] < {level}
       9947 + df['entry_signal'] = df['oversold']""",
       9948 +         params={"fast": [23], "slow": [50], "cycle": [10], "level": [25, 30]},
       9949 +         direction="long",
       9950 +         lookback=70,
       9951 +         indicators=["MACD", "EMA"],
       9952 +         combinable_with=["volume", "confirmation"],
       9953 +         strategy_type="STC",
       9954 +     ),
       9955 +     # STC Rising
       9956 +     PatternBlock(
       9957 +         id="STC_RISING",
       9958 +         name="STC Rising from Low",
       9959 +         category="schaff_trend",
       9960 +         formula_template="""df['macd'], _, _ = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod=9)
       9961 + df['macd_min'] = df['macd'].rolling({cycle}).min()
       9962 + df['macd_max'] = df['macd'].rolling({cycle}).max()
       9963 + df['stoch_macd'] = (df['macd'] - df['macd_min']) / (df['macd_max'] - df['macd_min'] + 1e-10) * 100
       9964 + df['stc1'] = ta.EMA(df['stoch_macd'], timeperiod=3)
       9965 + df['stc1_min'] = df['stc1'].rolling({cycle}).min()
       9966 + df['stc1_max'] = df['stc1'].rolling({cycle}).max()
       9967 + df['stc'] = (df['stc1'] - df['stc1_min']) / (df['stc1_max'] - df['stc1_min'] + 1e-10) * 100
       9968 + df['was_low'] = df['stc'].shift(1) < {low_level}
       9969 + df['rising'] = df['stc'] > df['stc'].shift(1)
       9970 + df['entry_signal'] = df['was_low'] & df['rising']""",
       9971 +         params={"fast": [23], "slow": [50], "cycle": [10], "low_level": [25, 30]},
       9972 +         direction="long",
       9973 +         lookback=70,
       9974 +         indicators=["MACD", "EMA"],
       9975 +         combinable_with=["momentum", "threshold"],
       9976 +         strategy_type="STC",
       9977 +     ),
       9978 +     # STC Trend Confirm
       9979 +     PatternBlock(
       9980 +         id="STC_TREND_CONFIRM",
       9981 +         name="STC Trend Confirm",
       9982 +         category="schaff_trend",
       9983 +         formula_template="""df['macd'], _, _ = ta.MACD(df['close'], fastperiod={fast}, slowperiod={slow}, signalperiod=9)
       9984 + df['macd_min'] = df['macd'].rolling({cycle}).min()
       9985 + df['macd_max'] = df['macd'].rolling({cycle}).max()
       9986 + df['stoch_macd'] = (df['macd'] - df['macd_min']) / (df['macd_max'] - df['macd_min'] + 1e-10) * 100
       9987 + df['stc1'] = ta.EMA(df['stoch_macd'], timeperiod=3)
       9988 + df['stc1_min'] = df['stc1'].rolling({cycle}).min()
       9989 + df['stc1_max'] = df['stc1'].rolling({cycle}).max()
       9990 + df['stc'] = (df['stc1'] - df['stc1_min']) / (df['stc1_max'] - df['stc1_min'] + 1e-10) * 100
       9991 + df['strong_up'] = df['stc'] > {high_level}
       9992 + df['price_up'] = df['close'] > df['close'].shift(3)
       9993 + df['entry_signal'] = df['strong_up'] & df['price_up']""",
       9994 +         params={"fast": [23], "slow": [50], "cycle": [10], "high_level": [70, 75]},
       9995 +         direction="long",
       9996 +         lookback=70,
       9997 +         indicators=["MACD", "EMA"],
       9998 +         combinable_with=["volume", "confirmation"],
       9999 +         strategy_type="STC",
      10000 +     ),
      10001 + ]
      10002 +
      10003 +
      10004 + # =============================================================================
      10005 + # FISHER TRANSFORM BLOCKS
      10006 + # =============================================================================
      10007 +
      10008 + FISHER_TRANSFORM_BLOCKS = [
      10009 +     # Fisher Oversold
      10010 +     PatternBlock(
      10011 +         id="FISHER_OVERSOLD",
      10012 +         name="Fisher Oversold",
      10013 +         category="fisher_transform",
      10014 +         formula_template="""df['hl2'] = (df['high'] + df['low']) / 2
      10015 + df['max_hl2'] = df['hl2'].rolling({period}).max()
      10016 + df['min_hl2'] = df['hl2'].rolling({period}).min()
      10017 + df['raw'] = 2 * ((df['hl2'] - df['min_hl2']) / (df['max_hl2'] - df['min_hl2'] + 1e-10) - 0.5)
      10018 + df['raw'] = df['raw'].clip(-0.999, 0.999)
      10019 + df['fisher'] = 0.5 * np.log((1 + df['raw']) / (1 - df['raw'] + 1e-10))
      10020 + df['fisher'] = ta.EMA(df['fisher'], timeperiod=3)
      10021 + df['oversold'] = df['fisher'] < {level}
      10022 + df['entry_signal'] = df['oversold']""",
      10023 +         params={"period": [10], "level": [-1.5, -2.0]},
      10024 +         direction="long",
      10025 +         lookback=25,
      10026 +         indicators=["EMA"],
      10027 +         combinable_with=["volume", "confirmation"],
      10028 +         strategy_type="FSH",
      10029 +     ),
      10030 +     # Fisher Cross Up
      10031 +     PatternBlock(
      10032 +         id="FISHER_CROSS_UP",
      10033 +         name="Fisher Cross Up",
      10034 +         category="fisher_transform",
      10035 +         formula_template="""df['hl2'] = (df['high'] + df['low']) / 2
      10036 + df['max_hl2'] = df['hl2'].rolling({period}).max()
      10037 + df['min_hl2'] = df['hl2'].rolling({period}).min()
      10038 + df['raw'] = 2 * ((df['hl2'] - df['min_hl2']) / (df['max_hl2'] - df['min_hl2'] + 1e-10) - 0.5)
      10039 + df['raw'] = df['raw'].clip(-0.999, 0.999)
      10040 + df['fisher'] = 0.5 * np.log((1 + df['raw']) / (1 - df['raw'] + 1e-10))
      10041 + df['fisher'] = ta.EMA(df['fisher'], timeperiod=3)
      10042 + df['signal'] = df['fisher'].shift(1)
      10043 + df['cross_up'] = (df['fisher'] > df['signal']) & (df['fisher'].shift(1) <= df['signal'].shift(1))
      10044 + df['entry_signal'] = df['cross_up']""",
      10045 +         params={"period": [10]},
      10046 +         direction="long",
      10047 +         lookback=25,
      10048 +         indicators=["EMA"],
      10049 +         combinable_with=["momentum", "threshold"],
      10050 +         strategy_type="FSH",
      10051 +     ),
      10052 +     # Fisher Zero Cross
      10053 +     PatternBlock(
      10054 +         id="FISHER_ZERO_CROSS",
      10055 +         name="Fisher Zero Cross Up",
      10056 +         category="fisher_transform",
      10057 +         formula_template="""df['hl2'] = (df['high'] + df['low']) / 2
      10058 + df['max_hl2'] = df['hl2'].rolling({period}).max()
      10059 + df['min_hl2'] = df['hl2'].rolling({period}).min()
      10060 + df['raw'] = 2 * ((df['hl2'] - df['min_hl2']) / (df['max_hl2'] - df['min_hl2'] + 1e-10) - 0.5)
      10061 + df['raw'] = df['raw'].clip(-0.999, 0.999)
      10062 + df['fisher'] = 0.5 * np.log((1 + df['raw']) / (1 - df['raw'] + 1e-10))
      10063 + df['fisher'] = ta.EMA(df['fisher'], timeperiod=3)
      10064 + df['cross_zero'] = (df['fisher'] > 0) & (df['fisher'].shift(1) <= 0)
      10065 + df['entry_signal'] = df['cross_zero']""",
      10066 +         params={"period": [10]},
      10067 +         direction="long",
      10068 +         lookback=25,
      10069 +         indicators=["EMA"],
      10070 +         combinable_with=["volume", "confirmation"],
      10071 +         strategy_type="FSH",
      10072 +     ),
      10073 + ]
      10074 +
      10075 +
      10076 + # =============================================================================
      10077 + # EHLERS BLOCKS (Super Smoother, etc.)
      10078 + # =============================================================================
      10079 +
      10080 + EHLERS_BLOCKS = [
      10081 +     # Super Smoother Cross
      10082 +     PatternBlock(
      10083 +         id="SUPER_SMOOTHER_CROSS",
      10084 +         name="Super Smoother Cross Up",
      10085 +         category="ehlers",
      10086 +         formula_template="""df['a1'] = np.exp(-1.414 * 3.14159 / {period})
      10087 + df['b1'] = 2 * df['a1'] * np.cos(1.414 * 3.14159 / {period})
      10088 + df['c2'] = df['b1']
      10089 + df['c3'] = -df['a1'] * df['a1']
      10090 + df['c1'] = 1 - df['c2'] - df['c3']
      10091 + df['ss'] = df['close'].copy()
      10092 + for i in range(2, len(df)):
      10093 +     df.iloc[i, df.columns.get_loc('ss')] = df['c1'].iloc[i] * (df['close'].iloc[i] + df['close'].iloc[i-1]) / 2 + df['c2'].iloc[i]
            + * df['ss'].iloc[i-1] + df['c3'].iloc[i] * df['ss'].iloc[i-2]
      10094 + df['cross_up'] = (df['close'] > df['ss']) & (df['close'].shift(1) <= df['ss'].shift(1))
      10095 + df['entry_signal'] = df['cross_up']""",
      10096 +         params={"period": [10, 20]},
      10097 +         direction="long",
      10098 +         lookback=30,
      10099 +         indicators=[],
      10100 +         combinable_with=["volume", "momentum"],
      10101 +         strategy_type="EHL",
      10102 +     ),
      10103 +     # Ehlers Trend
      10104 +     PatternBlock(
      10105 +         id="EHLERS_TREND",
      10106 +         name="Ehlers Smoothed Trend",
      10107 +         category="ehlers",
      10108 +         formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
      10109 + df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
      10110 + df['trend'] = df['ema_fast'] - df['ema_slow']
      10111 + df['trend_smooth'] = ta.EMA(df['trend'], timeperiod=5)
      10112 + df['trend_up'] = df['trend_smooth'] > 0
      10113 + df['trend_rising'] = df['trend_smooth'] > df['trend_smooth'].shift(1)
      10114 + df['entry_signal'] = df['trend_up'] & df['trend_rising']""",
      10115 +         params={"fast": [8, 10], "slow": [21, 25]},
      10116 +         direction="long",
      10117 +         lookback=35,
      10118 +         indicators=["EMA"],
      10119 +         combinable_with=["confirmation", "threshold"],
      10120 +         strategy_type="EHL",
      10121 +     ),
      10122 +     # Ehlers Instantaneous Trend
      10123 +     PatternBlock(
      10124 +         id="EHLERS_INST_TREND",
      10125 +         name="Ehlers Instantaneous Trend",
      10126 +         category="ehlers",
      10127 +         formula_template="""df['ema1'] = ta.EMA(df['close'], timeperiod={period})
      10128 + df['ema2'] = ta.EMA(df['ema1'], timeperiod={period})
      10129 + df['inst_trend'] = 2 * df['ema1'] - df['ema2']
      10130 + df['trigger'] = ta.EMA(df['inst_trend'], timeperiod=3)
      10131 + df['cross_up'] = (df['inst_trend'] > df['trigger']) & (df['inst_trend'].shift(1) <= df['trigger'].shift(1))
      10132 + df['entry_signal'] = df['cross_up']""",
      10133 +         params={"period": [10, 14]},
      10134 +         direction="long",
      10135 +         lookback=30,
      10136 +         indicators=["EMA"],
      10137 +         combinable_with=["volume", "momentum"],
      10138 +         strategy_type="EHL",
      10139 +     ),
      10140 + ]
      10141 +
      10142 +
      10143 + # =============================================================================
      10144 + # CENTER OF GRAVITY BLOCKS
      10145 + # =============================================================================
      10146 +
      10147 + CENTER_OF_GRAVITY_BLOCKS = [
      10148 +     # COG Oversold
      10149 +     PatternBlock(
      10150 +         id="COG_OVERSOLD",
      10151 +         name="COG Oversold",
      10152 +         category="center_of_gravity",
      10153 +         formula_template="""weights = np.arange(1, {period} + 1)
      10154 + df['cog'] = -df['close'].rolling({period}).apply(lambda x: np.sum(weights * x) / np.sum(x), raw=True)
      10155 + df['cog_norm'] = (df['cog'] - df['cog'].rolling(50).mean()) / (df['cog'].rolling(50).std() + 1e-10)
      10156 + df['oversold'] = df['cog_norm'] < {level}
      10157 + df['entry_signal'] = df['oversold']""",
      10158 +         params={"period": [10], "level": [-1.5, -2.0]},
      10159 +         direction="long",
      10160 +         lookback=60,
      10161 +         indicators=[],
      10162 +         combinable_with=["volume", "confirmation"],
      10163 +         strategy_type="COG",
      10164 +     ),
      10165 +     # COG Zero Cross
      10166 +     PatternBlock(
      10167 +         id="COG_ZERO_CROSS",
      10168 +         name="COG Zero Cross Up",
      10169 +         category="center_of_gravity",
      10170 +         formula_template="""weights = np.arange(1, {period} + 1)
      10171 + df['cog'] = -df['close'].rolling({period}).apply(lambda x: np.sum(weights * x) / np.sum(x), raw=True)
      10172 + df['cog_ma'] = df['cog'].rolling(10).mean()
      10173 + df['cross_up'] = (df['cog'] > df['cog_ma']) & (df['cog'].shift(1) <= df['cog_ma'].shift(1))
      10174 + df['entry_signal'] = df['cross_up']""",
      10175 +         params={"period": [10]},
      10176 +         direction="long",
      10177 +         lookback=30,
      10178 +         indicators=[],
      10179 +         combinable_with=["momentum", "threshold"],
      10180 +         strategy_type="COG",
      10181 +     ),
      10182 +     # COG Momentum
      10183 +     PatternBlock(
      10184 +         id="COG_MOMENTUM",
      10185 +         name="COG Momentum",
      10186 +         category="center_of_gravity",
      10187 +         formula_template="""weights = np.arange(1, {period} + 1)
      10188 + df['cog'] = -df['close'].rolling({period}).apply(lambda x: np.sum(weights * x) / np.sum(x), raw=True)
      10189 + df['cog_change'] = df['cog'] - df['cog'].shift(3)
      10190 + df['positive_mom'] = df['cog_change'] > 0
      10191 + df['accelerating'] = df['cog_change'] > df['cog_change'].shift(1)
      10192 + df['entry_signal'] = df['positive_mom'] & df['accelerating']""",
      10193 +         params={"period": [10, 14]},
      10194 +         direction="long",
      10195 +         lookback=30,
      10196 +         indicators=[],
      10197 +         combinable_with=["volume", "confirmation"],
      10198 +         strategy_type="COG",
      10199 +     ),
      10200 + ]
      10201 +
      10202 +
      10203 + # =============================================================================
      10204 + # RELATIVE VIGOR INDEX BLOCKS
      10205 + # =============================================================================
      10206 +
      10207 + RELATIVE_VIGOR_BLOCKS = [
      10208 +     # RVI Cross Up
      10209 +     PatternBlock(
      10210 +         id="RVI_CROSS_UP",
      10211 +         name="RVI Cross Up",
      10212 +         category="relative_vigor",
      10213 +         formula_template="""df['co'] = df['close'] - df['open']
      10214 + df['hl'] = df['high'] - df['low']
      10215 + df['rvi_num'] = (df['co'] + 2*df['co'].shift(1) + 2*df['co'].shift(2) + df['co'].shift(3)) / 6
      10216 + df['rvi_den'] = (df['hl'] + 2*df['hl'].shift(1) + 2*df['hl'].shift(2) + df['hl'].shift(3)) / 6
      10217 + df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
      10218 + df['signal'] = (df['rvi'] + 2*df['rvi'].shift(1) + 2*df['rvi'].shift(2) + df['rvi'].shift(3)) / 6
      10219 + df['cross_up'] = (df['rvi'] > df['signal']) & (df['rvi'].shift(1) <= df['signal'].shift(1))
      10220 + df['entry_signal'] = df['cross_up']""",
      10221 +         params={"period": [10, 14]},
      10222 +         direction="long",
      10223 +         lookback=30,
      10224 +         indicators=[],
      10225 +         combinable_with=["volume", "momentum"],
      10226 +         strategy_type="RVI",
      10227 +     ),
      10228 +     # RVI Positive
      10229 +     PatternBlock(
      10230 +         id="RVI_POSITIVE",
      10231 +         name="RVI Positive Zone",
      10232 +         category="relative_vigor",
      10233 +         formula_template="""df['co'] = df['close'] - df['open']
      10234 + df['hl'] = df['high'] - df['low']
      10235 + df['rvi_num'] = (df['co'] + 2*df['co'].shift(1) + 2*df['co'].shift(2) + df['co'].shift(3)) / 6
      10236 + df['rvi_den'] = (df['hl'] + 2*df['hl'].shift(1) + 2*df['hl'].shift(2) + df['hl'].shift(3)) / 6
      10237 + df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
      10238 + df['positive'] = df['rvi'] > 0
      10239 + df['rising'] = df['rvi'] > df['rvi'].shift(1)
      10240 + df['entry_signal'] = df['positive'] & df['rising']""",
      10241 +         params={"period": [10]},
      10242 +         direction="long",
      10243 +         lookback=25,
      10244 +         indicators=[],
      10245 +         combinable_with=["threshold", "confirmation"],
      10246 +         strategy_type="RVI",
      10247 +     ),
      10248 +     # RVI Divergence
      10249 +     PatternBlock(
      10250 +         id="RVI_DIVERGENCE",
      10251 +         name="RVI Divergence",
      10252 +         category="relative_vigor",
      10253 +         formula_template="""df['co'] = df['close'] - df['open']
      10254 + df['hl'] = df['high'] - df['low']
      10255 + df['rvi_num'] = (df['co'] + 2*df['co'].shift(1) + 2*df['co'].shift(2) + df['co'].shift(3)) / 6
      10256 + df['rvi_den'] = (df['hl'] + 2*df['hl'].shift(1) + 2*df['hl'].shift(2) + df['hl'].shift(3)) / 6
      10257 + df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
      10258 + df['price_lower'] = df['close'] < df['close'].shift(5)
      10259 + df['rvi_higher'] = df['rvi'] > df['rvi'].shift(5)
      10260 + df['divergence'] = df['price_lower'] & df['rvi_higher']
      10261 + df['entry_signal'] = df['divergence']""",
      10262 +         params={"period": [10]},
      10263 +         direction="long",
      10264 +         lookback=30,
      10265 +         indicators=[],
      10266 +         combinable_with=["volume", "confirmation"],
      10267 +         strategy_type="RVI",
      10268 +     ),
      10269 + ]
      10270 +
      10271 +
      10272 + # =============================================================================
      10273 + # RAINBOW MA BLOCKS
      10274 + # =============================================================================
      10275 +
      10276 + RAINBOW_MA_BLOCKS = [
      10277 +     # Rainbow Bull Alignment
      10278 +     PatternBlock(
      10279 +         id="RAINBOW_BULL_ALIGN",
      10280 +         name="Rainbow Bull Alignment",
      10281 +         category="rainbow_ma",
      10282 +         formula_template="""df['ma1'] = ta.SMA(df['close'], timeperiod={base})
      10283 + df['ma2'] = ta.SMA(df['ma1'], timeperiod={base})
      10284 + df['ma3'] = ta.SMA(df['ma2'], timeperiod={base})
      10285 + df['ma4'] = ta.SMA(df['ma3'], timeperiod={base})
      10286 + df['aligned'] = (df['close'] > df['ma1']) & (df['ma1'] > df['ma2']) & (df['ma2'] > df['ma3']) & (df['ma3'] > df['ma4'])
      10287 + df['entry_signal'] = df['aligned']""",
      10288 +         params={"base": [2, 3]},
      10289 +         direction="long",
      10290 +         lookback=30,
      10291 +         indicators=["SMA"],
      10292 +         combinable_with=["volume", "momentum"],
      10293 +         strategy_type="RBW",
      10294 +     ),
      10295 +     # Rainbow Cross
      10296 +     PatternBlock(
      10297 +         id="RAINBOW_CROSS",
      10298 +         name="Rainbow Cross Up",
      10299 +         category="rainbow_ma",
      10300 +         formula_template="""df['ma1'] = ta.SMA(df['close'], timeperiod={base})
      10301 + df['ma2'] = ta.SMA(df['ma1'], timeperiod={base})
      10302 + df['ma3'] = ta.SMA(df['ma2'], timeperiod={base})
      10303 + df['price_cross'] = (df['close'] > df['ma1']) & (df['close'].shift(1) <= df['ma1'].shift(1))
      10304 + df['ma_positive'] = df['ma1'] > df['ma2']
      10305 + df['entry_signal'] = df['price_cross'] & df['ma_positive']""",
      10306 +         params={"base": [2, 3]},
      10307 +         direction="long",
      10308 +         lookback=25,
      10309 +         indicators=["SMA"],
      10310 +         combinable_with=["confirmation", "threshold"],
      10311 +         strategy_type="RBW",
      10312 +     ),
      10313 +     # Rainbow Width
      10314 +     PatternBlock(
      10315 +         id="RAINBOW_WIDTH",
      10316 +         name="Rainbow Width Expanding",
      10317 +         category="rainbow_ma",
      10318 +         formula_template="""df['ma1'] = ta.SMA(df['close'], timeperiod={base})
      10319 + df['ma2'] = ta.SMA(df['ma1'], timeperiod={base})
      10320 + df['ma3'] = ta.SMA(df['ma2'], timeperiod={base})
      10321 + df['width'] = (df['ma1'] - df['ma3']) / df['close']
      10322 + df['expanding'] = df['width'] > df['width'].shift(3)
      10323 + df['positive'] = df['width'] > 0
      10324 + df['entry_signal'] = df['expanding'] & df['positive']""",
      10325 +         params={"base": [2, 3]},
      10326 +         direction="long",
      10327 +         lookback=30,
      10328 +         indicators=["SMA"],
      10329 +         combinable_with=["volume", "momentum"],
      10330 +         strategy_type="RBW",
      10331 +     ),
      10332 + ]
      10333 +
      10334 +
      10335 + # =============================================================================
      10336 + # TREND INTENSITY BLOCKS
      10337 + # =============================================================================
      10338 +
      10339 + TREND_INTENSITY_BLOCKS = [
      10340 +     # Trend Intensity High
      10341 +     PatternBlock(
      10342 +         id="TREND_INTENSITY_HIGH",
      10343 +         name="Trend Intensity High",
      10344 +         category="trend_intensity",
      10345 +         formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
      10346 + df['dev'] = abs(df['close'] - df['sma'])
      10347 + df['avg_dev'] = df['dev'].rolling({period}).mean()
      10348 + df['ti'] = df['dev'] / (df['avg_dev'] + 1e-10)
      10349 + df['high_ti'] = df['ti'] > {threshold}
      10350 + df['uptrend'] = df['close'] > df['sma']
      10351 + df['entry_signal'] = df['high_ti'] & df['uptrend']""",
      10352 +         params={"period": [20, 30], "threshold": [1.2, 1.5]},
      10353 +         direction="long",
      10354 +         lookback=40,
      10355 +         indicators=["SMA"],
      10356 +         combinable_with=["volume", "momentum"],
      10357 +         strategy_type="TIN",
      10358 +     ),
      10359 +     # Trend Intensity Rising
      10360 +     PatternBlock(
      10361 +         id="TREND_INTENSITY_RISING",
      10362 +         name="Trend Intensity Rising",
      10363 +         category="trend_intensity",
      10364 +         formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
      10365 + df['dev'] = abs(df['close'] - df['sma'])
      10366 + df['avg_dev'] = df['dev'].rolling({period}).mean()
      10367 + df['ti'] = df['dev'] / (df['avg_dev'] + 1e-10)
      10368 + df['ti_rising'] = df['ti'] > df['ti'].shift(3)
      10369 + df['uptrend'] = df['close'] > df['sma']
      10370 + df['entry_signal'] = df['ti_rising'] & df['uptrend']""",
      10371 +         params={"period": [20]},
      10372 +         direction="long",
      10373 +         lookback=35,
      10374 +         indicators=["SMA"],
      10375 +         combinable_with=["confirmation", "threshold"],
      10376 +         strategy_type="TIN",
      10377 +     ),
      10378 +     # Trend Intensity Breakout
      10379 +     PatternBlock(
      10380 +         id="TREND_INTENSITY_BREAK",
      10381 +         name="Trend Intensity Breakout",
      10382 +         category="trend_intensity",
      10383 +         formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
      10384 + df['dev'] = abs(df['close'] - df['sma'])
      10385 + df['avg_dev'] = df['dev'].rolling({period}).mean()
      10386 + df['ti'] = df['dev'] / (df['avg_dev'] + 1e-10)
      10387 + df['was_low'] = df['ti'].shift(3) < 0.8
      10388 + df['now_high'] = df['ti'] > {threshold}
      10389 + df['uptrend'] = df['close'] > df['sma']
      10390 + df['entry_signal'] = df['was_low'] & df['now_high'] & df['uptrend']""",
      10391 +         params={"period": [20], "threshold": [1.2, 1.3]},
      10392 +         direction="long",
      10393 +         lookback=40,
      10394 +         indicators=["SMA"],
      10395 +         combinable_with=["volume", "confirmation"],
      10396 +         strategy_type="TIN",
      10397 +     ),
      10398 + ]
      10399 +
      10400 +
      10401 + # =============================================================================
      10402 + # PRICE ZONE OSCILLATOR BLOCKS
      10403 + # =============================================================================
      10404 +
      10405 + PRICE_ZONE_OSC_BLOCKS = [
      10406 +     # PZO Oversold
      10407 +     PatternBlock(
      10408 +         id="PZO_OVERSOLD",
      10409 +         name="PZO Oversold",
      10410 +         category="price_zone_osc",
      10411 +         formula_template="""df['cp'] = np.where(df['close'] > df['close'].shift(1), df['close'], -df['close'])
      10412 + df['tc'] = ta.EMA(df['cp'], timeperiod={period})
      10413 + df['vc'] = ta.EMA(df['close'], timeperiod={period})
      10414 + df['pzo'] = 100 * df['tc'] / (df['vc'] + 1e-10)
      10415 + df['oversold'] = df['pzo'] < {level}
      10416 + df['entry_signal'] = df['oversold']""",
      10417 +         params={"period": [14], "level": [-40, -50]},
      10418 +         direction="long",
      10419 +         lookback=25,
      10420 +         indicators=["EMA"],
      10421 +         combinable_with=["volume", "confirmation"],
      10422 +         strategy_type="PZO",
      10423 +     ),
      10424 +     # PZO Cross Up
      10425 +     PatternBlock(
      10426 +         id="PZO_CROSS_UP",
      10427 +         name="PZO Cross Up Zero",
      10428 +         category="price_zone_osc",
      10429 +         formula_template="""df['cp'] = np.where(df['close'] > df['close'].shift(1), df['close'], -df['close'])
      10430 + df['tc'] = ta.EMA(df['cp'], timeperiod={period})
      10431 + df['vc'] = ta.EMA(df['close'], timeperiod={period})
      10432 + df['pzo'] = 100 * df['tc'] / (df['vc'] + 1e-10)
      10433 + df['cross_up'] = (df['pzo'] > 0) & (df['pzo'].shift(1) <= 0)
      10434 + df['entry_signal'] = df['cross_up']""",
      10435 +         params={"period": [14]},
      10436 +         direction="long",
      10437 +         lookback=25,
      10438 +         indicators=["EMA"],
      10439 +         combinable_with=["momentum", "threshold"],
      10440 +         strategy_type="PZO",
      10441 +     ),
      10442 +     # PZO Strong Positive
      10443 +     PatternBlock(
      10444 +         id="PZO_STRONG_POS",
      10445 +         name="PZO Strong Positive",
      10446 +         category="price_zone_osc",
      10447 +         formula_template="""df['cp'] = np.where(df['close'] > df['close'].shift(1), df['close'], -df['close'])
      10448 + df['tc'] = ta.EMA(df['cp'], timeperiod={period})
      10449 + df['vc'] = ta.EMA(df['close'], timeperiod={period})
      10450 + df['pzo'] = 100 * df['tc'] / (df['vc'] + 1e-10)
      10451 + df['strong_pos'] = df['pzo'] > {level}
      10452 + df['rising'] = df['pzo'] > df['pzo'].shift(1)
      10453 + df['entry_signal'] = df['strong_pos'] & df['rising']""",
      10454 +         params={"period": [14], "level": [40, 50]},
      10455 +         direction="long",
      10456 +         lookback=25,
      10457 +         indicators=["EMA"],
      10458 +         combinable_with=["volume", "confirmation"],
      10459 +         strategy_type="PZO",
      10460 +     ),
      10461 + ]
      10462 +
      10463 +
      10464 + # =============================================================================
      10465   # ALL BLOCKS COMBINED
      10466   # =============================================================================
      10467

● Ora aggiorno ALL_BLOCKS.

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      10600       + PRICE_ACTION_ZONES_BLOCKS
      10601       + TWIN_RANGE_BLOCKS
      10602       + IMPULSE_MACD_BLOCKS
      10603 +     + WAVETREND_BLOCKS
      10604 +     + QQE_BLOCKS
      10605 +     + SCHAFF_TREND_BLOCKS
      10606 +     + FISHER_TRANSFORM_BLOCKS
      10607 +     + EHLERS_BLOCKS
      10608 +     + CENTER_OF_GRAVITY_BLOCKS
      10609 +     + RELATIVE_VIGOR_BLOCKS
      10610 +     + RAINBOW_MA_BLOCKS
      10611 +     + TREND_INTENSITY_BLOCKS
      10612 +     + PRICE_ZONE_OSC_BLOCKS
      10613   )
      10614
      10615   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python -c "
      from src.generator.pattern_gen.building_blocks import ALL_BLOCKS, BLOCKS_BY_CATEGORY…)
  ⎿  Total blocks: 538
     Categories: 143
     … +23 lines (ctrl+o to expand)

● Round 14 completato!

  Risultati:
  - Blocchi totali: 538 (da 508, +30)
  - Categorie: 143 (da 133, +10)
  - Validazione: 200/200 OK
  - Lookahead: 0 problemi
  - Strategie stimate: ~114,024

  ---
  Altre possibili migliorie (Round 15)?

  Potrei aggiungere altri ~30 blocchi:

  1. SUPERTREND_BLOCKS (3) - Supertrend indicator signals
  2. HURST_EXPONENT_BLOCKS (3) - Trend vs mean-reversion detection
  3. CHANDELIER_EXIT_BLOCKS (3) - ATR-based trailing stop signals
  4. ELDER_IMPULSE_BLOCKS (3) - Elder's impulse system color
  5. DMI_ADX_EXT_BLOCKS (3) - DMI/ADX extended patterns
  6. ALMA_BLOCKS (3) - Arnaud Legoux MA signals
  7. VIDYA_BLOCKS (3) - Variable Index Dynamic Average
  8. MCGINLEY_BLOCKS (3) - McGinley Dynamic indicator
  9. T3_MA_BLOCKS (3) - Tillson T3 moving average
  10. JURIK_MA_BLOCKS (3) - Jurik-style adaptive MA

  Totale: +30 blocchi → 568 blocchi, ~121,000+ strategie

  Vuoi che implementi?

✻ Worked for 2m 37s

❯ si

● Search(pattern: "PRICE_ZONE_OSC_BLOCKS = \[", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 60 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 691 lines
      10462
      10463
      10464   # =============================================================================
      10465 + # SUPERTREND BLOCKS
      10466 + # =============================================================================
      10467 +
      10468 + SUPERTREND_BLOCKS = [
      10469 +     # Supertrend Buy Signal
      10470 +     PatternBlock(
      10471 +         id="SUPERTREND_BUY",
      10472 +         name="Supertrend Buy",
      10473 +         category="supertrend",
      10474 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      10475 + df['hl2'] = (df['high'] + df['low']) / 2
      10476 + df['upper'] = df['hl2'] + df['atr'] * {mult}
      10477 + df['lower'] = df['hl2'] - df['atr'] * {mult}
      10478 + df['trend'] = 1
      10479 + df['st'] = df['lower'].copy()
      10480 + for i in range(1, len(df)):
      10481 +     if df['close'].iloc[i-1] > df['st'].iloc[i-1]:
      10482 +         df.iloc[i, df.columns.get_loc('st')] = max(df['lower'].iloc[i], df['st'].iloc[i-1])
      10483 +     else:
      10484 +         df.iloc[i, df.columns.get_loc('st')] = df['upper'].iloc[i]
      10485 + df['buy'] = (df['close'] > df['st']) & (df['close'].shift(1) <= df['st'].shift(1))
      10486 + df['entry_signal'] = df['buy']""",
      10487 +         params={"period": [10], "mult": [2.0, 3.0]},
      10488 +         direction="long",
      10489 +         lookback=30,
      10490 +         indicators=["ATR"],
      10491 +         combinable_with=["volume", "momentum"],
      10492 +         strategy_type="SPT",
      10493 +     ),
      10494 +     # Supertrend Trend Up
      10495 +     PatternBlock(
      10496 +         id="SUPERTREND_UP",
      10497 +         name="Supertrend Trend Up",
      10498 +         category="supertrend",
      10499 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      10500 + df['hl2'] = (df['high'] + df['low']) / 2
      10501 + df['basic_upper'] = df['hl2'] + df['atr'] * {mult}
      10502 + df['basic_lower'] = df['hl2'] - df['atr'] * {mult}
      10503 + df['in_uptrend'] = df['close'] > df['basic_lower']
      10504 + df['uptrend_confirm'] = df['in_uptrend'].rolling(3).sum() >= 3
      10505 + df['entry_signal'] = df['uptrend_confirm']""",
      10506 +         params={"period": [10], "mult": [2.0, 3.0]},
      10507 +         direction="long",
      10508 +         lookback=25,
      10509 +         indicators=["ATR"],
      10510 +         combinable_with=["confirmation", "threshold"],
      10511 +         strategy_type="SPT",
      10512 +     ),
      10513 +     # Supertrend Proximity
      10514 +     PatternBlock(
      10515 +         id="SUPERTREND_PROXIMITY",
      10516 +         name="Supertrend Proximity",
      10517 +         category="supertrend",
      10518 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      10519 + df['hl2'] = (df['high'] + df['low']) / 2
      10520 + df['lower_band'] = df['hl2'] - df['atr'] * {mult}
      10521 + df['dist'] = (df['close'] - df['lower_band']) / df['close']
      10522 + df['close_to_band'] = df['dist'] < {proximity}
      10523 + df['above'] = df['close'] > df['lower_band']
      10524 + df['entry_signal'] = df['close_to_band'] & df['above']""",
      10525 +         params={"period": [10], "mult": [2.0], "proximity": [0.01, 0.015]},
      10526 +         direction="long",
      10527 +         lookback=25,
      10528 +         indicators=["ATR"],
      10529 +         combinable_with=["volume", "confirmation"],
      10530 +         strategy_type="SPT",
      10531 +     ),
      10532 + ]
      10533 +
      10534 +
      10535 + # =============================================================================
      10536 + # HURST EXPONENT BLOCKS (simplified)
      10537 + # =============================================================================
      10538 +
      10539 + HURST_EXPONENT_BLOCKS = [
      10540 +     # Hurst Trending
      10541 +     PatternBlock(
      10542 +         id="HURST_TRENDING",
      10543 +         name="Hurst Trending",
      10544 +         category="hurst_exponent",
      10545 +         formula_template="""df['returns'] = df['close'].pct_change()
      10546 + df['std_n'] = df['returns'].rolling({period}).std()
      10547 + df['std_2n'] = df['returns'].rolling({period} * 2).std()
      10548 + df['hurst_proxy'] = np.log(df['std_2n'] / (df['std_n'] + 1e-10)) / np.log(2)
      10549 + df['trending'] = df['hurst_proxy'] > {threshold}
      10550 + df['uptrend'] = df['close'] > df['close'].shift({period})
      10551 + df['entry_signal'] = df['trending'] & df['uptrend']""",
      10552 +         params={"period": [20], "threshold": [0.55, 0.6]},
      10553 +         direction="long",
      10554 +         lookback=50,
      10555 +         indicators=[],
      10556 +         combinable_with=["momentum", "volume"],
      10557 +         strategy_type="HRS",
      10558 +     ),
      10559 +     # Hurst Mean Reverting
      10560 +     PatternBlock(
      10561 +         id="HURST_MEAN_REV",
      10562 +         name="Hurst Mean Reverting",
      10563 +         category="hurst_exponent",
      10564 +         formula_template="""df['returns'] = df['close'].pct_change()
      10565 + df['std_n'] = df['returns'].rolling({period}).std()
      10566 + df['std_2n'] = df['returns'].rolling({period} * 2).std()
      10567 + df['hurst_proxy'] = np.log(df['std_2n'] / (df['std_n'] + 1e-10)) / np.log(2)
      10568 + df['mean_rev'] = df['hurst_proxy'] < {threshold}
      10569 + df['oversold'] = df['close'] < df['close'].rolling({period}).mean()
      10570 + df['entry_signal'] = df['mean_rev'] & df['oversold']""",
      10571 +         params={"period": [20], "threshold": [0.4, 0.45]},
      10572 +         direction="long",
      10573 +         lookback=50,
      10574 +         indicators=[],
      10575 +         combinable_with=["confirmation", "threshold"],
      10576 +         strategy_type="HRS",
      10577 +     ),
      10578 +     # Hurst Regime Change
      10579 +     PatternBlock(
      10580 +         id="HURST_REGIME_CHANGE",
      10581 +         name="Hurst Regime Change",
      10582 +         category="hurst_exponent",
      10583 +         formula_template="""df['returns'] = df['close'].pct_change()
      10584 + df['std_n'] = df['returns'].rolling({period}).std()
      10585 + df['std_2n'] = df['returns'].rolling({period} * 2).std()
      10586 + df['hurst_proxy'] = np.log(df['std_2n'] / (df['std_n'] + 1e-10)) / np.log(2)
      10587 + df['was_mean_rev'] = df['hurst_proxy'].shift(5) < 0.45
      10588 + df['now_trending'] = df['hurst_proxy'] > 0.55
      10589 + df['entry_signal'] = df['was_mean_rev'] & df['now_trending']""",
      10590 +         params={"period": [20]},
      10591 +         direction="bidi",
      10592 +         lookback=50,
      10593 +         indicators=[],
      10594 +         combinable_with=["momentum", "volume"],
      10595 +         strategy_type="HRS",
      10596 +     ),
      10597 + ]
      10598 +
      10599 +
      10600 + # =============================================================================
      10601 + # CHANDELIER EXIT BLOCKS
      10602 + # =============================================================================
      10603 +
      10604 + CHANDELIER_EXIT_BLOCKS = [
      10605 +     # Chandelier Long Entry
      10606 +     PatternBlock(
      10607 +         id="CHANDELIER_LONG_ENTRY",
      10608 +         name="Chandelier Long Entry",
      10609 +         category="chandelier_exit",
      10610 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      10611 + df['highest'] = df['high'].rolling({period}).max()
      10612 + df['chandelier_long'] = df['highest'] - df['atr'] * {mult}
      10613 + df['above'] = df['close'] > df['chandelier_long']
      10614 + df['cross_above'] = df['above'] & ~df['above'].shift(1)
      10615 + df['entry_signal'] = df['cross_above']""",
      10616 +         params={"period": [22], "mult": [3.0]},
      10617 +         direction="long",
      10618 +         lookback=35,
      10619 +         indicators=["ATR"],
      10620 +         combinable_with=["volume", "momentum"],
      10621 +         strategy_type="CHN",
      10622 +     ),
      10623 +     # Chandelier Trend Confirm
      10624 +     PatternBlock(
      10625 +         id="CHANDELIER_TREND",
      10626 +         name="Chandelier Trend Confirm",
      10627 +         category="chandelier_exit",
      10628 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      10629 + df['highest'] = df['high'].rolling({period}).max()
      10630 + df['chandelier_long'] = df['highest'] - df['atr'] * {mult}
      10631 + df['above'] = df['close'] > df['chandelier_long']
      10632 + df['trend_days'] = df['above'].rolling(5).sum() >= 4
      10633 + df['entry_signal'] = df['trend_days']""",
      10634 +         params={"period": [22], "mult": [3.0]},
      10635 +         direction="long",
      10636 +         lookback=35,
      10637 +         indicators=["ATR"],
      10638 +         combinable_with=["confirmation", "threshold"],
      10639 +         strategy_type="CHN",
      10640 +     ),
      10641 +     # Chandelier Proximity
      10642 +     PatternBlock(
      10643 +         id="CHANDELIER_PROXIMITY",
      10644 +         name="Chandelier Proximity",
      10645 +         category="chandelier_exit",
      10646 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      10647 + df['highest'] = df['high'].rolling({period}).max()
      10648 + df['chandelier_long'] = df['highest'] - df['atr'] * {mult}
      10649 + df['dist'] = (df['close'] - df['chandelier_long']) / df['close']
      10650 + df['close_to_stop'] = df['dist'] < {proximity}
      10651 + df['above'] = df['close'] > df['chandelier_long']
      10652 + df['entry_signal'] = df['close_to_stop'] & df['above']""",
      10653 +         params={"period": [22], "mult": [3.0], "proximity": [0.02, 0.03]},
      10654 +         direction="long",
      10655 +         lookback=35,
      10656 +         indicators=["ATR"],
      10657 +         combinable_with=["volume", "confirmation"],
      10658 +         strategy_type="CHN",
      10659 +     ),
      10660 + ]
      10661 +
      10662 +
      10663 + # =============================================================================
      10664 + # ELDER IMPULSE BLOCKS
      10665 + # =============================================================================
      10666 +
      10667 + ELDER_IMPULSE_BLOCKS = [
      10668 +     # Elder Impulse Green
      10669 +     PatternBlock(
      10670 +         id="ELDER_IMPULSE_GREEN",
      10671 +         name="Elder Impulse Green",
      10672 +         category="elder_impulse",
      10673 +         formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
      10674 + df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
      10675 + df['ema_rising'] = df['ema'] > df['ema'].shift(1)
      10676 + df['hist_rising'] = df['hist'] > df['hist'].shift(1)
      10677 + df['green'] = df['ema_rising'] & df['hist_rising']
      10678 + df['entry_signal'] = df['green']""",
      10679 +         params={"period": [13]},
      10680 +         direction="long",
      10681 +         lookback=40,
      10682 +         indicators=["EMA", "MACD"],
      10683 +         combinable_with=["volume", "threshold"],
      10684 +         strategy_type="EIM",
      10685 +     ),
      10686 +     # Elder Impulse Green Start
      10687 +     PatternBlock(
      10688 +         id="ELDER_IMPULSE_GREEN_START",
      10689 +         name="Elder Impulse Green Start",
      10690 +         category="elder_impulse",
      10691 +         formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
      10692 + df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
      10693 + df['ema_rising'] = df['ema'] > df['ema'].shift(1)
      10694 + df['hist_rising'] = df['hist'] > df['hist'].shift(1)
      10695 + df['green'] = df['ema_rising'] & df['hist_rising']
      10696 + df['green_start'] = df['green'] & ~df['green'].shift(1)
      10697 + df['entry_signal'] = df['green_start']""",
      10698 +         params={"period": [13]},
      10699 +         direction="long",
      10700 +         lookback=40,
      10701 +         indicators=["EMA", "MACD"],
      10702 +         combinable_with=["volume", "confirmation"],
      10703 +         strategy_type="EIM",
      10704 +     ),
      10705 +     # Elder Impulse Blue to Green
      10706 +     PatternBlock(
      10707 +         id="ELDER_IMPULSE_BLUE_GREEN",
      10708 +         name="Elder Impulse Blue to Green",
      10709 +         category="elder_impulse",
      10710 +         formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
      10711 + df['macd'], df['signal'], df['hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
      10712 + df['ema_rising'] = df['ema'] > df['ema'].shift(1)
      10713 + df['hist_rising'] = df['hist'] > df['hist'].shift(1)
      10714 + df['green'] = df['ema_rising'] & df['hist_rising']
      10715 + df['blue'] = ~df['ema_rising'] & ~df['hist_rising'].shift(1).fillna(False) | ~df['hist_rising'] &
            +df['ema_rising'].shift(1).fillna(False)
      10716 + df['was_blue'] = ~df['green'].shift(1)
      10717 + df['now_green'] = df['green']
      10718 + df['entry_signal'] = df['was_blue'] & df['now_green']""",
      10719 +         params={"period": [13]},
      10720 +         direction="long",
      10721 +         lookback=40,
      10722 +         indicators=["EMA", "MACD"],
      10723 +         combinable_with=["momentum", "confirmation"],
      10724 +         strategy_type="EIM",
      10725 +     ),
      10726 + ]
      10727 +
      10728 +
      10729 + # =============================================================================
      10730 + # DMI ADX EXTENDED BLOCKS
      10731 + # =============================================================================
      10732 +
      10733 + DMI_ADX_EXT_BLOCKS = [
      10734 +     # DMI Cross with ADX Filter
      10735 +     PatternBlock(
      10736 +         id="DMI_CROSS_ADX_FILTER",
      10737 +         name="DMI Cross ADX Filter",
      10738 +         category="dmi_adx_ext",
      10739 +         formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
      10740 + df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
      10741 + df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod={period})
      10742 + df['cross_up'] = (df['plus_di'] > df['minus_di']) & (df['plus_di'].shift(1) <= df['minus_di'].shift(1))
      10743 + df['adx_strong'] = df['adx'] > {adx_thresh}
      10744 + df['entry_signal'] = df['cross_up'] & df['adx_strong']""",
      10745 +         params={"period": [14], "adx_thresh": [20, 25]},
      10746 +         direction="long",
      10747 +         lookback=30,
      10748 +         indicators=["PLUS_DI", "MINUS_DI", "ADX"],
      10749 +         combinable_with=["volume", "confirmation"],
      10750 +         strategy_type="DMX",
      10751 +     ),
      10752 +     # ADX Rising with DI+
      10753 +     PatternBlock(
      10754 +         id="ADX_RISING_DI_PLUS",
      10755 +         name="ADX Rising with DI+",
      10756 +         category="dmi_adx_ext",
      10757 +         formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
      10758 + df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
      10759 + df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod={period})
      10760 + df['adx_rising'] = df['adx'] > df['adx'].shift(3)
      10761 + df['di_positive'] = df['plus_di'] > df['minus_di']
      10762 + df['entry_signal'] = df['adx_rising'] & df['di_positive']""",
      10763 +         params={"period": [14]},
      10764 +         direction="long",
      10765 +         lookback=30,
      10766 +         indicators=["PLUS_DI", "MINUS_DI", "ADX"],
      10767 +         combinable_with=["momentum", "threshold"],
      10768 +         strategy_type="DMX",
      10769 +     ),
      10770 +     # DMI Spread Expanding
      10771 +     PatternBlock(
      10772 +         id="DMI_SPREAD_EXPAND",
      10773 +         name="DMI Spread Expanding",
      10774 +         category="dmi_adx_ext",
      10775 +         formula_template="""df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
      10776 + df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod={period})
      10777 + df['spread'] = df['plus_di'] - df['minus_di']
      10778 + df['spread_expand'] = df['spread'] > df['spread'].shift(3)
      10779 + df['positive_spread'] = df['spread'] > {threshold}
      10780 + df['entry_signal'] = df['spread_expand'] & df['positive_spread']""",
      10781 +         params={"period": [14], "threshold": [5, 10]},
      10782 +         direction="long",
      10783 +         lookback=30,
      10784 +         indicators=["PLUS_DI", "MINUS_DI"],
      10785 +         combinable_with=["volume", "confirmation"],
      10786 +         strategy_type="DMX",
      10787 +     ),
      10788 + ]
      10789 +
      10790 +
      10791 + # =============================================================================
      10792 + # ALMA BLOCKS (Arnaud Legoux MA)
      10793 + # =============================================================================
      10794 +
      10795 + ALMA_BLOCKS = [
      10796 +     # ALMA Cross Up
      10797 +     PatternBlock(
      10798 +         id="ALMA_CROSS_UP",
      10799 +         name="ALMA Cross Up",
      10800 +         category="alma",
      10801 +         formula_template="""m = {offset} * ({period} - 1)
      10802 + s = {period} / {sigma}
      10803 + weights = np.exp(-((np.arange({period}) - m) ** 2) / (2 * s * s))
      10804 + weights = weights / weights.sum()
      10805 + df['alma'] = df['close'].rolling({period}).apply(lambda x: np.sum(weights * x), raw=True)
      10806 + df['cross_up'] = (df['close'] > df['alma']) & (df['close'].shift(1) <= df['alma'].shift(1))
      10807 + df['entry_signal'] = df['cross_up']""",
      10808 +         params={"period": [9, 14], "offset": [0.85], "sigma": [6]},
      10809 +         direction="long",
      10810 +         lookback=25,
      10811 +         indicators=[],
      10812 +         combinable_with=["volume", "momentum"],
      10813 +         strategy_type="ALM",
      10814 +     ),
      10815 +     # ALMA Trend
      10816 +     PatternBlock(
      10817 +         id="ALMA_TREND",
      10818 +         name="ALMA Trend Up",
      10819 +         category="alma",
      10820 +         formula_template="""m = {offset} * ({period} - 1)
      10821 + s = {period} / {sigma}
      10822 + weights = np.exp(-((np.arange({period}) - m) ** 2) / (2 * s * s))
      10823 + weights = weights / weights.sum()
      10824 + df['alma'] = df['close'].rolling({period}).apply(lambda x: np.sum(weights * x), raw=True)
      10825 + df['above'] = df['close'] > df['alma']
      10826 + df['alma_rising'] = df['alma'] > df['alma'].shift(3)
      10827 + df['entry_signal'] = df['above'] & df['alma_rising']""",
      10828 +         params={"period": [9], "offset": [0.85], "sigma": [6]},
      10829 +         direction="long",
      10830 +         lookback=25,
      10831 +         indicators=[],
      10832 +         combinable_with=["confirmation", "threshold"],
      10833 +         strategy_type="ALM",
      10834 +     ),
      10835 +     # ALMA Distance
      10836 +     PatternBlock(
      10837 +         id="ALMA_DISTANCE",
      10838 +         name="ALMA Distance Extreme",
      10839 +         category="alma",
      10840 +         formula_template="""m = {offset} * ({period} - 1)
      10841 + s = {period} / {sigma}
      10842 + weights = np.exp(-((np.arange({period}) - m) ** 2) / (2 * s * s))
      10843 + weights = weights / weights.sum()
      10844 + df['alma'] = df['close'].rolling({period}).apply(lambda x: np.sum(weights * x), raw=True)
      10845 + df['dist'] = (df['close'] - df['alma']) / df['alma']
      10846 + df['extreme_low'] = df['dist'] < -{threshold}
      10847 + df['entry_signal'] = df['extreme_low']""",
      10848 +         params={"period": [14], "offset": [0.85], "sigma": [6], "threshold": [0.02, 0.03]},
      10849 +         direction="long",
      10850 +         lookback=30,
      10851 +         indicators=[],
      10852 +         combinable_with=["volume", "confirmation"],
      10853 +         strategy_type="ALM",
      10854 +     ),
      10855 + ]
      10856 +
      10857 +
      10858 + # =============================================================================
      10859 + # VIDYA BLOCKS (Variable Index Dynamic Average)
      10860 + # =============================================================================
      10861 +
      10862 + VIDYA_BLOCKS = [
      10863 +     # VIDYA Cross Up
      10864 +     PatternBlock(
      10865 +         id="VIDYA_CROSS_UP",
      10866 +         name="VIDYA Cross Up",
      10867 +         category="vidya",
      10868 +         formula_template="""df['cmo'] = ta.CMO(df['close'], timeperiod={cmo_period})
      10869 + df['abs_cmo'] = abs(df['cmo']) / 100
      10870 + df['sc'] = 2 / ({period} + 1)
      10871 + df['vidya'] = df['close'].copy()
      10872 + for i in range(1, len(df)):
      10873 +     df.iloc[i, df.columns.get_loc('vidya')] = df['sc'].iloc[i] * df['abs_cmo'].iloc[i] * df['close'].iloc[i] + (1 -
            +df['sc'].iloc[i] * df['abs_cmo'].iloc[i]) * df['vidya'].iloc[i-1]
      10874 + df['cross_up'] = (df['close'] > df['vidya']) & (df['close'].shift(1) <= df['vidya'].shift(1))
      10875 + df['entry_signal'] = df['cross_up']""",
      10876 +         params={"period": [14], "cmo_period": [9]},
      10877 +         direction="long",
      10878 +         lookback=30,
      10879 +         indicators=["CMO"],
      10880 +         combinable_with=["volume", "momentum"],
      10881 +         strategy_type="VDY",
      10882 +     ),
      10883 +     # VIDYA Trend
      10884 +     PatternBlock(
      10885 +         id="VIDYA_TREND",
      10886 +         name="VIDYA Trend Up",
      10887 +         category="vidya",
      10888 +         formula_template="""df['cmo'] = ta.CMO(df['close'], timeperiod={cmo_period})
      10889 + df['abs_cmo'] = abs(df['cmo']) / 100
      10890 + df['sc'] = 2 / ({period} + 1)
      10891 + df['vidya'] = df['close'].copy()
      10892 + for i in range(1, len(df)):
      10893 +     df.iloc[i, df.columns.get_loc('vidya')] = df['sc'].iloc[i] * df['abs_cmo'].iloc[i] * df['close'].iloc[i] + (1 -
            +df['sc'].iloc[i] * df['abs_cmo'].iloc[i]) * df['vidya'].iloc[i-1]
      10894 + df['above'] = df['close'] > df['vidya']
      10895 + df['rising'] = df['vidya'] > df['vidya'].shift(3)
      10896 + df['entry_signal'] = df['above'] & df['rising']""",
      10897 +         params={"period": [14], "cmo_period": [9]},
      10898 +         direction="long",
      10899 +         lookback=30,
      10900 +         indicators=["CMO"],
      10901 +         combinable_with=["confirmation", "threshold"],
      10902 +         strategy_type="VDY",
      10903 +     ),
      10904 +     # VIDYA Momentum Strong
      10905 +     PatternBlock(
      10906 +         id="VIDYA_MOMENTUM",
      10907 +         name="VIDYA Momentum Strong",
      10908 +         category="vidya",
      10909 +         formula_template="""df['cmo'] = ta.CMO(df['close'], timeperiod={cmo_period})
      10910 + df['abs_cmo'] = abs(df['cmo']) / 100
      10911 + df['strong_cmo'] = df['abs_cmo'] > {threshold}
      10912 + df['cmo_positive'] = df['cmo'] > 0
      10913 + df['entry_signal'] = df['strong_cmo'] & df['cmo_positive']""",
      10914 +         params={"cmo_period": [9], "threshold": [0.4, 0.5]},
      10915 +         direction="long",
      10916 +         lookback=20,
      10917 +         indicators=["CMO"],
      10918 +         combinable_with=["volume", "confirmation"],
      10919 +         strategy_type="VDY",
      10920 +     ),
      10921 + ]
      10922 +
      10923 +
      10924 + # =============================================================================
      10925 + # MCGINLEY DYNAMIC BLOCKS
      10926 + # =============================================================================
      10927 +
      10928 + MCGINLEY_BLOCKS = [
      10929 +     # McGinley Cross Up
      10930 +     PatternBlock(
      10931 +         id="MCGINLEY_CROSS_UP",
      10932 +         name="McGinley Cross Up",
      10933 +         category="mcginley",
      10934 +         formula_template="""df['md'] = df['close'].copy()
      10935 + k = 0.6
      10936 + n = {period}
      10937 + for i in range(1, len(df)):
      10938 +     prev_md = df['md'].iloc[i-1]
      10939 +     curr_close = df['close'].iloc[i]
      10940 +     ratio = curr_close / (prev_md + 1e-10)
      10941 +     df.iloc[i, df.columns.get_loc('md')] = prev_md + (curr_close - prev_md) / (n * (ratio ** 4) + 1e-10)
      10942 + df['cross_up'] = (df['close'] > df['md']) & (df['close'].shift(1) <= df['md'].shift(1))
      10943 + df['entry_signal'] = df['cross_up']""",
      10944 +         params={"period": [10, 14]},
      10945 +         direction="long",
      10946 +         lookback=30,
      10947 +         indicators=[],
      10948 +         combinable_with=["volume", "momentum"],
      10949 +         strategy_type="MCG",
      10950 +     ),
      10951 +     # McGinley Trend
      10952 +     PatternBlock(
      10953 +         id="MCGINLEY_TREND",
      10954 +         name="McGinley Trend Up",
      10955 +         category="mcginley",
      10956 +         formula_template="""df['md'] = df['close'].copy()
      10957 + n = {period}
      10958 + for i in range(1, len(df)):
      10959 +     prev_md = df['md'].iloc[i-1]
      10960 +     curr_close = df['close'].iloc[i]
      10961 +     ratio = curr_close / (prev_md + 1e-10)
      10962 +     df.iloc[i, df.columns.get_loc('md')] = prev_md + (curr_close - prev_md) / (n * (ratio ** 4) + 1e-10)
      10963 + df['above'] = df['close'] > df['md']
      10964 + df['md_rising'] = df['md'] > df['md'].shift(3)
      10965 + df['entry_signal'] = df['above'] & df['md_rising']""",
      10966 +         params={"period": [10]},
      10967 +         direction="long",
      10968 +         lookback=30,
      10969 +         indicators=[],
      10970 +         combinable_with=["confirmation", "threshold"],
      10971 +         strategy_type="MCG",
      10972 +     ),
      10973 +     # McGinley Proximity
      10974 +     PatternBlock(
      10975 +         id="MCGINLEY_PROXIMITY",
      10976 +         name="McGinley Proximity",
      10977 +         category="mcginley",
      10978 +         formula_template="""df['md'] = df['close'].copy()
      10979 + n = {period}
      10980 + for i in range(1, len(df)):
      10981 +     prev_md = df['md'].iloc[i-1]
      10982 +     curr_close = df['close'].iloc[i]
      10983 +     ratio = curr_close / (prev_md + 1e-10)
      10984 +     df.iloc[i, df.columns.get_loc('md')] = prev_md + (curr_close - prev_md) / (n * (ratio ** 4) + 1e-10)
      10985 + df['dist'] = abs(df['close'] - df['md']) / df['close']
      10986 + df['close_to_md'] = df['dist'] < {threshold}
      10987 + df['above'] = df['close'] > df['md']
      10988 + df['entry_signal'] = df['close_to_md'] & df['above']""",
      10989 +         params={"period": [10], "threshold": [0.005, 0.01]},
      10990 +         direction="long",
      10991 +         lookback=30,
      10992 +         indicators=[],
      10993 +         combinable_with=["volume", "confirmation"],
      10994 +         strategy_type="MCG",
      10995 +     ),
      10996 + ]
      10997 +
      10998 +
      10999 + # =============================================================================
      11000 + # T3 MA BLOCKS (Tillson)
      11001 + # =============================================================================
      11002 +
      11003 + T3_MA_BLOCKS = [
      11004 +     # T3 Cross Up
      11005 +     PatternBlock(
      11006 +         id="T3_CROSS_UP",
      11007 +         name="T3 Cross Up",
      11008 +         category="t3_ma",
      11009 +         formula_template="""vf = {vfactor}
      11010 + df['ema1'] = ta.EMA(df['close'], timeperiod={period})
      11011 + df['ema2'] = ta.EMA(df['ema1'], timeperiod={period})
      11012 + df['ema3'] = ta.EMA(df['ema2'], timeperiod={period})
      11013 + df['ema4'] = ta.EMA(df['ema3'], timeperiod={period})
      11014 + df['ema5'] = ta.EMA(df['ema4'], timeperiod={period})
      11015 + df['ema6'] = ta.EMA(df['ema5'], timeperiod={period})
      11016 + c1 = -vf**3
      11017 + c2 = 3*vf**2 + 3*vf**3
      11018 + c3 = -6*vf**2 - 3*vf - 3*vf**3
      11019 + c4 = 1 + 3*vf + vf**3 + 3*vf**2
      11020 + df['t3'] = c1*df['ema6'] + c2*df['ema5'] + c3*df['ema4'] + c4*df['ema3']
      11021 + df['cross_up'] = (df['close'] > df['t3']) & (df['close'].shift(1) <= df['t3'].shift(1))
      11022 + df['entry_signal'] = df['cross_up']""",
      11023 +         params={"period": [5], "vfactor": [0.7]},
      11024 +         direction="long",
      11025 +         lookback=40,
      11026 +         indicators=["EMA"],
      11027 +         combinable_with=["volume", "momentum"],
      11028 +         strategy_type="T3M",
      11029 +     ),
      11030 +     # T3 Trend
      11031 +     PatternBlock(
      11032 +         id="T3_TREND",
      11033 +         name="T3 Trend Up",
      11034 +         category="t3_ma",
      11035 +         formula_template="""vf = {vfactor}
      11036 + df['ema1'] = ta.EMA(df['close'], timeperiod={period})
      11037 + df['ema2'] = ta.EMA(df['ema1'], timeperiod={period})
      11038 + df['ema3'] = ta.EMA(df['ema2'], timeperiod={period})
      11039 + df['ema4'] = ta.EMA(df['ema3'], timeperiod={period})
      11040 + df['ema5'] = ta.EMA(df['ema4'], timeperiod={period})
      11041 + df['ema6'] = ta.EMA(df['ema5'], timeperiod={period})
      11042 + c1 = -vf**3
      11043 + c2 = 3*vf**2 + 3*vf**3
      11044 + c3 = -6*vf**2 - 3*vf - 3*vf**3
      11045 + c4 = 1 + 3*vf + vf**3 + 3*vf**2
      11046 + df['t3'] = c1*df['ema6'] + c2*df['ema5'] + c3*df['ema4'] + c4*df['ema3']
      11047 + df['above'] = df['close'] > df['t3']
      11048 + df['rising'] = df['t3'] > df['t3'].shift(3)
      11049 + df['entry_signal'] = df['above'] & df['rising']""",
      11050 +         params={"period": [5], "vfactor": [0.7]},
      11051 +         direction="long",
      11052 +         lookback=40,
      11053 +         indicators=["EMA"],
      11054 +         combinable_with=["confirmation", "threshold"],
      11055 +         strategy_type="T3M",
      11056 +     ),
      11057 +     # T3 Slope Strong
      11058 +     PatternBlock(
      11059 +         id="T3_SLOPE",
      11060 +         name="T3 Slope Strong",
      11061 +         category="t3_ma",
      11062 +         formula_template="""vf = {vfactor}
      11063 + df['ema1'] = ta.EMA(df['close'], timeperiod={period})
      11064 + df['ema2'] = ta.EMA(df['ema1'], timeperiod={period})
      11065 + df['ema3'] = ta.EMA(df['ema2'], timeperiod={period})
      11066 + df['ema4'] = ta.EMA(df['ema3'], timeperiod={period})
      11067 + df['ema5'] = ta.EMA(df['ema4'], timeperiod={period})
      11068 + df['ema6'] = ta.EMA(df['ema5'], timeperiod={period})
      11069 + c1 = -vf**3
      11070 + c2 = 3*vf**2 + 3*vf**3
      11071 + c3 = -6*vf**2 - 3*vf - 3*vf**3
      11072 + c4 = 1 + 3*vf + vf**3 + 3*vf**2
      11073 + df['t3'] = c1*df['ema6'] + c2*df['ema5'] + c3*df['ema4'] + c4*df['ema3']
      11074 + df['slope'] = (df['t3'] - df['t3'].shift(3)) / df['t3'].shift(3)
      11075 + df['strong_up'] = df['slope'] > {threshold}
      11076 + df['entry_signal'] = df['strong_up']""",
      11077 +         params={"period": [5], "vfactor": [0.7], "threshold": [0.01, 0.015]},
      11078 +         direction="long",
      11079 +         lookback=40,
      11080 +         indicators=["EMA"],
      11081 +         combinable_with=["volume", "confirmation"],
      11082 +         strategy_type="T3M",
      11083 +     ),
      11084 + ]
      11085 +
      11086 +
      11087 + # =============================================================================
      11088 + # JURIK MA BLOCKS (simplified adaptive)
      11089 + # =============================================================================
      11090 +
      11091 + JURIK_MA_BLOCKS = [
      11092 +     # Jurik Cross Up
      11093 +     PatternBlock(
      11094 +         id="JURIK_CROSS_UP",
      11095 +         name="Jurik Cross Up",
      11096 +         category="jurik_ma",
      11097 +         formula_template="""df['vol'] = df['close'].rolling({period}).std()
      11098 + df['vol_ratio'] = df['vol'] / df['vol'].rolling({period} * 2).mean()
      11099 + df['alpha'] = df['vol_ratio'].clip(0.1, 1.0)
      11100 + df['jma'] = df['close'].copy()
      11101 + for i in range(1, len(df)):
      11102 +     a = df['alpha'].iloc[i] * {phase}
      11103 +     df.iloc[i, df.columns.get_loc('jma')] = a * df['close'].iloc[i] + (1 - a) * df['jma'].iloc[i-1]
      11104 + df['cross_up'] = (df['close'] > df['jma']) & (df['close'].shift(1) <= df['jma'].shift(1))
      11105 + df['entry_signal'] = df['cross_up']""",
      11106 +         params={"period": [10], "phase": [0.5]},
      11107 +         direction="long",
      11108 +         lookback=35,
      11109 +         indicators=[],
      11110 +         combinable_with=["volume", "momentum"],
      11111 +         strategy_type="JMA",
      11112 +     ),
      11113 +     # Jurik Trend
      11114 +     PatternBlock(
      11115 +         id="JURIK_TREND",
      11116 +         name="Jurik Trend Up",
      11117 +         category="jurik_ma",
      11118 +         formula_template="""df['vol'] = df['close'].rolling({period}).std()
      11119 + df['vol_ratio'] = df['vol'] / df['vol'].rolling({period} * 2).mean()
      11120 + df['alpha'] = df['vol_ratio'].clip(0.1, 1.0)
      11121 + df['jma'] = df['close'].copy()
      11122 + for i in range(1, len(df)):
      11123 +     a = df['alpha'].iloc[i] * {phase}
      11124 +     df.iloc[i, df.columns.get_loc('jma')] = a * df['close'].iloc[i] + (1 - a) * df['jma'].iloc[i-1]
      11125 + df['above'] = df['close'] > df['jma']
      11126 + df['jma_rising'] = df['jma'] > df['jma'].shift(3)
      11127 + df['entry_signal'] = df['above'] & df['jma_rising']""",
      11128 +         params={"period": [10], "phase": [0.5]},
      11129 +         direction="long",
      11130 +         lookback=35,
      11131 +         indicators=[],
      11132 +         combinable_with=["confirmation", "threshold"],
      11133 +         strategy_type="JMA",
      11134 +     ),
      11135 +     # Jurik Adaptive
      11136 +     PatternBlock(
      11137 +         id="JURIK_ADAPTIVE",
      11138 +         name="Jurik Adaptive Entry",
      11139 +         category="jurik_ma",
      11140 +         formula_template="""df['vol'] = df['close'].rolling({period}).std()
      11141 + df['vol_ratio'] = df['vol'] / df['vol'].rolling({period} * 2).mean()
      11142 + df['high_adapt'] = df['vol_ratio'] > 1.0
      11143 + df['trend_up'] = df['close'] > df['close'].shift(5)
      11144 + df['entry_signal'] = df['high_adapt'] & df['trend_up']""",
      11145 +         params={"period": [10, 14]},
      11146 +         direction="long",
      11147 +         lookback=35,
      11148 +         indicators=[],
      11149 +         combinable_with=["volume", "momentum"],
      11150 +         strategy_type="JMA",
      11151 +     ),
      11152 + ]
      11153 +
      11154 +
      11155 + # =============================================================================
      11156   # ALL BLOCKS COMBINED
      11157   # =============================================================================
      11158

● Ora aggiorno ALL_BLOCKS.

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      11301       + RAINBOW_MA_BLOCKS
      11302       + TREND_INTENSITY_BLOCKS
      11303       + PRICE_ZONE_OSC_BLOCKS
      11304 +     + SUPERTREND_BLOCKS
      11305 +     + HURST_EXPONENT_BLOCKS
      11306 +     + CHANDELIER_EXIT_BLOCKS
      11307 +     + ELDER_IMPULSE_BLOCKS
      11308 +     + DMI_ADX_EXT_BLOCKS
      11309 +     + ALMA_BLOCKS
      11310 +     + VIDYA_BLOCKS
      11311 +     + MCGINLEY_BLOCKS
      11312 +     + T3_MA_BLOCKS
      11313 +     + JURIK_MA_BLOCKS
      11314   )
      11315
      11316   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python -c "
      from src.generator.pattern_gen.building_blocks import ALL_BLOCKS, BLOCKS_BY_CATEGORY…)
  ⎿  Total blocks: 568
     Categories: 153
     … +23 lines (ctrl+o to expand)

● Round 15 completato!

  Risultati:
  - Blocchi totali: 568 (da 538, +30)
  - Categorie: 153 (da 143, +10)
  - Validazione: 200/200 OK
  - Lookahead: 0 problemi
  - Strategie stimate: ~118,312

  ---
  Altre possibili migliorie (Round 16)?

  Potrei aggiungere altri ~30 blocchi:

  1. ZERO_LAG_MA_BLOCKS (3) - Zero-lag EMA signals
  2. HULL_MA_BLOCKS (3) - Hull Moving Average
  3. LAGUERRE_BLOCKS (3) - Laguerre RSI/filter
  4. STOCHASTIC_EXT_BLOCKS (3) - Extended stochastic patterns
  5. WILLIAMS_AD_BLOCKS (3) - Williams Accumulation/Distribution
  6. POSITIVE_VOLUME_BLOCKS (3) - Positive Volume Index
  7. NEGATIVE_VOLUME_BLOCKS (3) - Negative Volume Index
  8. INERTIA_BLOCKS (3) - Inertia indicator
  9. KNOW_SURE_THING_BLOCKS (3) - KST oscillator
  10. SPECIAL_K_BLOCKS (3) - Special K indicator

  Totale: +30 blocchi → 598 blocchi, ~125,000+ strategie

  Vuoi che implementi?

✻ Cogitated for 2m 25s

❯ si

● Search(pattern: "JURIK_MA_BLOCKS = \[", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 60 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 671 lines
      11153
      11154
      11155   # =============================================================================
      11156 + # ZERO LAG MA BLOCKS
      11157 + # =============================================================================
      11158 +
      11159 + ZERO_LAG_MA_BLOCKS = [
      11160 +     # Zero Lag EMA Cross Up
      11161 +     PatternBlock(
      11162 +         id="ZLEMA_CROSS_UP",
      11163 +         name="Zero Lag EMA Cross Up",
      11164 +         category="zero_lag_ma",
      11165 +         formula_template="""lag = ({period} - 1) // 2
      11166 + df['zlema_data'] = 2 * df['close'] - df['close'].shift(lag)
      11167 + df['zlema'] = ta.EMA(df['zlema_data'], timeperiod={period})
      11168 + df['cross_up'] = (df['close'] > df['zlema']) & (df['close'].shift(1) <= df['zlema'].shift(1))
      11169 + df['entry_signal'] = df['cross_up']""",
      11170 +         params={"period": [10, 20]},
      11171 +         direction="long",
      11172 +         lookback=30,
      11173 +         indicators=["EMA"],
      11174 +         combinable_with=["volume", "momentum"],
      11175 +         strategy_type="ZLM",
      11176 +     ),
      11177 +     # Zero Lag EMA Trend
      11178 +     PatternBlock(
      11179 +         id="ZLEMA_TREND",
      11180 +         name="Zero Lag EMA Trend",
      11181 +         category="zero_lag_ma",
      11182 +         formula_template="""lag = ({period} - 1) // 2
      11183 + df['zlema_data'] = 2 * df['close'] - df['close'].shift(lag)
      11184 + df['zlema'] = ta.EMA(df['zlema_data'], timeperiod={period})
      11185 + df['above'] = df['close'] > df['zlema']
      11186 + df['rising'] = df['zlema'] > df['zlema'].shift(3)
      11187 + df['entry_signal'] = df['above'] & df['rising']""",
      11188 +         params={"period": [12, 20]},
      11189 +         direction="long",
      11190 +         lookback=35,
      11191 +         indicators=["EMA"],
      11192 +         combinable_with=["confirmation", "threshold"],
      11193 +         strategy_type="ZLM",
      11194 +     ),
      11195 +     # Zero Lag Dual Cross
      11196 +     PatternBlock(
      11197 +         id="ZLEMA_DUAL_CROSS",
      11198 +         name="Zero Lag Dual Cross",
      11199 +         category="zero_lag_ma",
      11200 +         formula_template="""lag_fast = ({fast} - 1) // 2
      11201 + lag_slow = ({slow} - 1) // 2
      11202 + df['zl_fast_data'] = 2 * df['close'] - df['close'].shift(lag_fast)
      11203 + df['zl_slow_data'] = 2 * df['close'] - df['close'].shift(lag_slow)
      11204 + df['zlema_fast'] = ta.EMA(df['zl_fast_data'], timeperiod={fast})
      11205 + df['zlema_slow'] = ta.EMA(df['zl_slow_data'], timeperiod={slow})
      11206 + df['cross_up'] = (df['zlema_fast'] > df['zlema_slow']) & (df['zlema_fast'].shift(1) <= df['zlema_slow'].shift(1))
      11207 + df['entry_signal'] = df['cross_up']""",
      11208 +         params={"fast": [8], "slow": [21]},
      11209 +         direction="long",
      11210 +         lookback=35,
      11211 +         indicators=["EMA"],
      11212 +         combinable_with=["volume", "confirmation"],
      11213 +         strategy_type="ZLM",
      11214 +     ),
      11215 + ]
      11216 +
      11217 +
      11218 + # =============================================================================
      11219 + # HULL MA BLOCKS
      11220 + # =============================================================================
      11221 +
      11222 + HULL_MA_BLOCKS = [
      11223 +     # Hull MA Cross Up
      11224 +     PatternBlock(
      11225 +         id="HMA_CROSS_UP",
      11226 +         name="Hull MA Cross Up",
      11227 +         category="hull_ma",
      11228 +         formula_template="""half_period = {period} // 2
      11229 + sqrt_period = int(np.sqrt({period}))
      11230 + df['wma_half'] = ta.WMA(df['close'], timeperiod=half_period)
      11231 + df['wma_full'] = ta.WMA(df['close'], timeperiod={period})
      11232 + df['hma_raw'] = 2 * df['wma_half'] - df['wma_full']
      11233 + df['hma'] = ta.WMA(df['hma_raw'], timeperiod=sqrt_period)
      11234 + df['cross_up'] = (df['close'] > df['hma']) & (df['close'].shift(1) <= df['hma'].shift(1))
      11235 + df['entry_signal'] = df['cross_up']""",
      11236 +         params={"period": [9, 16]},
      11237 +         direction="long",
      11238 +         lookback=30,
      11239 +         indicators=["WMA"],
      11240 +         combinable_with=["volume", "momentum"],
      11241 +         strategy_type="HMA",
      11242 +     ),
      11243 +     # Hull MA Trend
      11244 +     PatternBlock(
      11245 +         id="HMA_TREND",
      11246 +         name="Hull MA Trend",
      11247 +         category="hull_ma",
      11248 +         formula_template="""half_period = {period} // 2
      11249 + sqrt_period = int(np.sqrt({period}))
      11250 + df['wma_half'] = ta.WMA(df['close'], timeperiod=half_period)
      11251 + df['wma_full'] = ta.WMA(df['close'], timeperiod={period})
      11252 + df['hma_raw'] = 2 * df['wma_half'] - df['wma_full']
      11253 + df['hma'] = ta.WMA(df['hma_raw'], timeperiod=sqrt_period)
      11254 + df['above'] = df['close'] > df['hma']
      11255 + df['rising'] = df['hma'] > df['hma'].shift(2)
      11256 + df['entry_signal'] = df['above'] & df['rising']""",
      11257 +         params={"period": [9, 14]},
      11258 +         direction="long",
      11259 +         lookback=30,
      11260 +         indicators=["WMA"],
      11261 +         combinable_with=["confirmation", "threshold"],
      11262 +         strategy_type="HMA",
      11263 +     ),
      11264 +     # Hull MA Color Change
      11265 +     PatternBlock(
      11266 +         id="HMA_COLOR_CHANGE",
      11267 +         name="Hull MA Color Change",
      11268 +         category="hull_ma",
      11269 +         formula_template="""half_period = {period} // 2
      11270 + sqrt_period = int(np.sqrt({period}))
      11271 + df['wma_half'] = ta.WMA(df['close'], timeperiod=half_period)
      11272 + df['wma_full'] = ta.WMA(df['close'], timeperiod={period})
      11273 + df['hma_raw'] = 2 * df['wma_half'] - df['wma_full']
      11274 + df['hma'] = ta.WMA(df['hma_raw'], timeperiod=sqrt_period)
      11275 + df['hma_rising'] = df['hma'] > df['hma'].shift(1)
      11276 + df['was_falling'] = df['hma'].shift(1) < df['hma'].shift(2)
      11277 + df['color_change'] = df['hma_rising'] & df['was_falling']
      11278 + df['entry_signal'] = df['color_change']""",
      11279 +         params={"period": [9, 16]},
      11280 +         direction="long",
      11281 +         lookback=30,
      11282 +         indicators=["WMA"],
      11283 +         combinable_with=["volume", "confirmation"],
      11284 +         strategy_type="HMA",
      11285 +     ),
      11286 + ]
      11287 +
      11288 +
      11289 + # =============================================================================
      11290 + # LAGUERRE BLOCKS
      11291 + # =============================================================================
      11292 +
      11293 + LAGUERRE_BLOCKS = [
      11294 +     # Laguerre RSI Oversold
      11295 +     PatternBlock(
      11296 +         id="LAGUERRE_RSI_OVERSOLD",
      11297 +         name="Laguerre RSI Oversold",
      11298 +         category="laguerre",
      11299 +         formula_template="""gamma = {gamma}
      11300 + df['L0'] = (1 - gamma) * df['close'] + gamma * df['close'].shift(1).fillna(df['close'])
      11301 + df['L1'] = -gamma * df['L0'] + df['L0'].shift(1).fillna(df['L0']) + gamma * df['L0'].shift(1).fillna(df['L0'])
      11302 + df['L2'] = -gamma * df['L1'] + df['L1'].shift(1).fillna(df['L1']) + gamma * df['L1'].shift(1).fillna(df['L1'])
      11303 + df['L3'] = -gamma * df['L2'] + df['L2'].shift(1).fillna(df['L2']) + gamma * df['L2'].shift(1).fillna(df['L2'])
      11304 + df['cu'] = np.where(df['L0'] >= df['L1'], df['L0'] - df['L1'], 0) + np.where(df['L1'] >= df['L2'], df['L1'] - df['L2'], 0) +
            +np.where(df['L2'] >= df['L3'], df['L2'] - df['L3'], 0)
      11305 + df['cd'] = np.where(df['L0'] < df['L1'], df['L1'] - df['L0'], 0) + np.where(df['L1'] < df['L2'], df['L2'] - df['L1'], 0) +
            +np.where(df['L2'] < df['L3'], df['L3'] - df['L2'], 0)
      11306 + df['lrsi'] = df['cu'] / (df['cu'] + df['cd'] + 1e-10)
      11307 + df['oversold'] = df['lrsi'] < {level}
      11308 + df['entry_signal'] = df['oversold']""",
      11309 +         params={"gamma": [0.7, 0.8], "level": [0.2, 0.25]},
      11310 +         direction="long",
      11311 +         lookback=20,
      11312 +         indicators=[],
      11313 +         combinable_with=["volume", "confirmation"],
      11314 +         strategy_type="LAG",
      11315 +     ),
      11316 +     # Laguerre RSI Cross Up
      11317 +     PatternBlock(
      11318 +         id="LAGUERRE_RSI_CROSS",
      11319 +         name="Laguerre RSI Cross Up",
      11320 +         category="laguerre",
      11321 +         formula_template="""gamma = {gamma}
      11322 + df['L0'] = (1 - gamma) * df['close'] + gamma * df['close'].shift(1).fillna(df['close'])
      11323 + df['L1'] = -gamma * df['L0'] + df['L0'].shift(1).fillna(df['L0']) + gamma * df['L0'].shift(1).fillna(df['L0'])
      11324 + df['L2'] = -gamma * df['L1'] + df['L1'].shift(1).fillna(df['L1']) + gamma * df['L1'].shift(1).fillna(df['L1'])
      11325 + df['L3'] = -gamma * df['L2'] + df['L2'].shift(1).fillna(df['L2']) + gamma * df['L2'].shift(1).fillna(df['L2'])
      11326 + df['cu'] = np.where(df['L0'] >= df['L1'], df['L0'] - df['L1'], 0) + np.where(df['L1'] >= df['L2'], df['L1'] - df['L2'], 0) +
            +np.where(df['L2'] >= df['L3'], df['L2'] - df['L3'], 0)
      11327 + df['cd'] = np.where(df['L0'] < df['L1'], df['L1'] - df['L0'], 0) + np.where(df['L1'] < df['L2'], df['L2'] - df['L1'], 0) +
            +np.where(df['L2'] < df['L3'], df['L3'] - df['L2'], 0)
      11328 + df['lrsi'] = df['cu'] / (df['cu'] + df['cd'] + 1e-10)
      11329 + df['cross_up'] = (df['lrsi'] > {level}) & (df['lrsi'].shift(1) <= {level})
      11330 + df['entry_signal'] = df['cross_up']""",
      11331 +         params={"gamma": [0.7], "level": [0.2, 0.3]},
      11332 +         direction="long",
      11333 +         lookback=20,
      11334 +         indicators=[],
      11335 +         combinable_with=["momentum", "threshold"],
      11336 +         strategy_type="LAG",
      11337 +     ),
      11338 +     # Laguerre RSI Rising
      11339 +     PatternBlock(
      11340 +         id="LAGUERRE_RSI_RISING",
      11341 +         name="Laguerre RSI Rising",
      11342 +         category="laguerre",
      11343 +         formula_template="""gamma = {gamma}
      11344 + df['L0'] = (1 - gamma) * df['close'] + gamma * df['close'].shift(1).fillna(df['close'])
      11345 + df['L1'] = -gamma * df['L0'] + df['L0'].shift(1).fillna(df['L0']) + gamma * df['L0'].shift(1).fillna(df['L0'])
      11346 + df['L2'] = -gamma * df['L1'] + df['L1'].shift(1).fillna(df['L1']) + gamma * df['L1'].shift(1).fillna(df['L1'])
      11347 + df['L3'] = -gamma * df['L2'] + df['L2'].shift(1).fillna(df['L2']) + gamma * df['L2'].shift(1).fillna(df['L2'])
      11348 + df['cu'] = np.where(df['L0'] >= df['L1'], df['L0'] - df['L1'], 0) + np.where(df['L1'] >= df['L2'], df['L1'] - df['L2'], 0) +
            +np.where(df['L2'] >= df['L3'], df['L2'] - df['L3'], 0)
      11349 + df['cd'] = np.where(df['L0'] < df['L1'], df['L1'] - df['L0'], 0) + np.where(df['L1'] < df['L2'], df['L2'] - df['L1'], 0) +
            +np.where(df['L2'] < df['L3'], df['L3'] - df['L2'], 0)
      11350 + df['lrsi'] = df['cu'] / (df['cu'] + df['cd'] + 1e-10)
      11351 + df['rising'] = df['lrsi'] > df['lrsi'].shift(1)
      11352 + df['above_mid'] = df['lrsi'] > 0.5
      11353 + df['entry_signal'] = df['rising'] & df['above_mid']""",
      11354 +         params={"gamma": [0.7, 0.8]},
      11355 +         direction="long",
      11356 +         lookback=20,
      11357 +         indicators=[],
      11358 +         combinable_with=["volume", "confirmation"],
      11359 +         strategy_type="LAG",
      11360 +     ),
      11361 + ]
      11362 +
      11363 +
      11364 + # =============================================================================
      11365 + # STOCHASTIC EXTENDED BLOCKS
      11366 + # =============================================================================
      11367 +
      11368 + STOCHASTIC_EXT_BLOCKS = [
      11369 +     # Stochastic Pop
      11370 +     PatternBlock(
      11371 +         id="STOCH_POP",
      11372 +         name="Stochastic Pop",
      11373 +         category="stochastic_ext",
      11374 +         formula_template="""df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period={period},
            +slowk_period=3, slowd_period=3)
      11375 + df['was_oversold'] = df['slowk'].shift(3) < {oversold}
      11376 + df['now_above'] = df['slowk'] > {pop_level}
      11377 + df['pop'] = df['was_oversold'] & df['now_above']
      11378 + df['entry_signal'] = df['pop']""",
      11379 +         params={"period": [14], "oversold": [20, 25], "pop_level": [50, 60]},
      11380 +         direction="long",
      11381 +         lookback=30,
      11382 +         indicators=["STOCH"],
      11383 +         combinable_with=["volume", "momentum"],
      11384 +         strategy_type="STE",
      11385 +     ),
      11386 +     # Stochastic Hook
      11387 +     PatternBlock(
      11388 +         id="STOCH_HOOK",
      11389 +         name="Stochastic Hook",
      11390 +         category="stochastic_ext",
      11391 +         formula_template="""df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period={period},
            +slowk_period=3, slowd_period=3)
      11392 + df['oversold'] = df['slowk'] < {level}
      11393 + df['k_turning'] = (df['slowk'] > df['slowk'].shift(1)) & (df['slowk'].shift(1) < df['slowk'].shift(2))
      11394 + df['hook'] = df['oversold'] & df['k_turning']
      11395 + df['entry_signal'] = df['hook']""",
      11396 +         params={"period": [14], "level": [20, 30]},
      11397 +         direction="long",
      11398 +         lookback=25,
      11399 +         indicators=["STOCH"],
      11400 +         combinable_with=["confirmation", "threshold"],
      11401 +         strategy_type="STE",
      11402 +     ),
      11403 +     # Stochastic Momentum
      11404 +     PatternBlock(
      11405 +         id="STOCH_MOMENTUM",
      11406 +         name="Stochastic Momentum",
      11407 +         category="stochastic_ext",
      11408 +         formula_template="""df['slowk'], df['slowd'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period={period},
            +slowk_period=3, slowd_period=3)
      11409 + df['k_momentum'] = df['slowk'] - df['slowk'].shift(5)
      11410 + df['strong_momentum'] = df['k_momentum'] > {threshold}
      11411 + df['k_above_d'] = df['slowk'] > df['slowd']
      11412 + df['entry_signal'] = df['strong_momentum'] & df['k_above_d']""",
      11413 +         params={"period": [14], "threshold": [20, 30]},
      11414 +         direction="long",
      11415 +         lookback=30,
      11416 +         indicators=["STOCH"],
      11417 +         combinable_with=["volume", "confirmation"],
      11418 +         strategy_type="STE",
      11419 +     ),
      11420 + ]
      11421 +
      11422 +
      11423 + # =============================================================================
      11424 + # WILLIAMS AD BLOCKS
      11425 + # =============================================================================
      11426 +
      11427 + WILLIAMS_AD_BLOCKS = [
      11428 +     # Williams AD Rising
      11429 +     PatternBlock(
      11430 +         id="WAD_RISING",
      11431 +         name="Williams AD Rising",
      11432 +         category="williams_ad",
      11433 +         formula_template="""df['trh'] = np.maximum(df['high'], df['close'].shift(1))
      11434 + df['trl'] = np.minimum(df['low'], df['close'].shift(1))
      11435 + df['ad'] = np.where(df['close'] > df['close'].shift(1), df['close'] - df['trl'], np.where(df['close'] < df['close'].shift(1),
            +df['close'] - df['trh'], 0))
      11436 + df['wad'] = df['ad'].cumsum()
      11437 + df['wad_ma'] = df['wad'].rolling({period}).mean()
      11438 + df['rising'] = df['wad'] > df['wad_ma']
      11439 + df['wad_up'] = df['wad'] > df['wad'].shift(3)
      11440 + df['entry_signal'] = df['rising'] & df['wad_up']""",
      11441 +         params={"period": [14, 20]},
      11442 +         direction="long",
      11443 +         lookback=30,
      11444 +         indicators=[],
      11445 +         combinable_with=["volume", "momentum"],
      11446 +         strategy_type="WAX",
      11447 +     ),
      11448 +     # Williams AD Divergence
      11449 +     PatternBlock(
      11450 +         id="WAD_DIVERGENCE",
      11451 +         name="Williams AD Divergence",
      11452 +         category="williams_ad",
      11453 +         formula_template="""df['trh'] = np.maximum(df['high'], df['close'].shift(1))
      11454 + df['trl'] = np.minimum(df['low'], df['close'].shift(1))
      11455 + df['ad'] = np.where(df['close'] > df['close'].shift(1), df['close'] - df['trl'], np.where(df['close'] < df['close'].shift(1),
            +df['close'] - df['trh'], 0))
      11456 + df['wad'] = df['ad'].cumsum()
      11457 + df['price_lower'] = df['close'] < df['close'].shift({lookback})
      11458 + df['wad_higher'] = df['wad'] > df['wad'].shift({lookback})
      11459 + df['divergence'] = df['price_lower'] & df['wad_higher']
      11460 + df['entry_signal'] = df['divergence']""",
      11461 +         params={"lookback": [5, 10]},
      11462 +         direction="long",
      11463 +         lookback=30,
      11464 +         indicators=[],
      11465 +         combinable_with=["confirmation", "threshold"],
      11466 +         strategy_type="WAX",
      11467 +     ),
      11468 +     # Williams AD Breakout
      11469 +     PatternBlock(
      11470 +         id="WAD_BREAKOUT",
      11471 +         name="Williams AD Breakout",
      11472 +         category="williams_ad",
      11473 +         formula_template="""df['trh'] = np.maximum(df['high'], df['close'].shift(1))
      11474 + df['trl'] = np.minimum(df['low'], df['close'].shift(1))
      11475 + df['ad'] = np.where(df['close'] > df['close'].shift(1), df['close'] - df['trl'], np.where(df['close'] < df['close'].shift(1),
            +df['close'] - df['trh'], 0))
      11476 + df['wad'] = df['ad'].cumsum()
      11477 + df['wad_high'] = df['wad'].rolling({period}).max()
      11478 + df['breakout'] = df['wad'] > df['wad_high'].shift(1)
      11479 + df['entry_signal'] = df['breakout']""",
      11480 +         params={"period": [20, 30]},
      11481 +         direction="long",
      11482 +         lookback=40,
      11483 +         indicators=[],
      11484 +         combinable_with=["volume", "confirmation"],
      11485 +         strategy_type="WAX",
      11486 +     ),
      11487 + ]
      11488 +
      11489 +
      11490 + # =============================================================================
      11491 + # POSITIVE VOLUME INDEX BLOCKS
      11492 + # =============================================================================
      11493 +
      11494 + POSITIVE_VOLUME_BLOCKS = [
      11495 +     # PVI Cross Up
      11496 +     PatternBlock(
      11497 +         id="PVI_CROSS_UP",
      11498 +         name="PVI Cross Up",
      11499 +         category="positive_volume",
      11500 +         formula_template="""df['vol_up'] = df['volume'] > df['volume'].shift(1)
      11501 + df['ret'] = df['close'].pct_change()
      11502 + df['pvi_change'] = np.where(df['vol_up'], df['ret'], 0)
      11503 + df['pvi'] = (1 + df['pvi_change']).cumprod() * 1000
      11504 + df['pvi_ma'] = ta.EMA(df['pvi'], timeperiod={period})
      11505 + df['cross_up'] = (df['pvi'] > df['pvi_ma']) & (df['pvi'].shift(1) <= df['pvi_ma'].shift(1))
      11506 + df['entry_signal'] = df['cross_up']""",
      11507 +         params={"period": [255]},
      11508 +         direction="long",
      11509 +         lookback=270,
      11510 +         indicators=["EMA"],
      11511 +         combinable_with=["momentum", "threshold"],
      11512 +         strategy_type="PVI",
      11513 +     ),
      11514 +     # PVI Above MA
      11515 +     PatternBlock(
      11516 +         id="PVI_ABOVE_MA",
      11517 +         name="PVI Above MA",
      11518 +         category="positive_volume",
      11519 +         formula_template="""df['vol_up'] = df['volume'] > df['volume'].shift(1)
      11520 + df['ret'] = df['close'].pct_change()
      11521 + df['pvi_change'] = np.where(df['vol_up'], df['ret'], 0)
      11522 + df['pvi'] = (1 + df['pvi_change']).cumprod() * 1000
      11523 + df['pvi_ma'] = ta.SMA(df['pvi'], timeperiod={period})
      11524 + df['above'] = df['pvi'] > df['pvi_ma']
      11525 + df['rising'] = df['pvi'] > df['pvi'].shift(5)
      11526 + df['entry_signal'] = df['above'] & df['rising']""",
      11527 +         params={"period": [100, 200]},
      11528 +         direction="long",
      11529 +         lookback=220,
      11530 +         indicators=["SMA"],
      11531 +         combinable_with=["volume", "confirmation"],
      11532 +         strategy_type="PVI",
      11533 +     ),
      11534 +     # PVI Rising Fast
      11535 +     PatternBlock(
      11536 +         id="PVI_RISING_FAST",
      11537 +         name="PVI Rising Fast",
      11538 +         category="positive_volume",
      11539 +         formula_template="""df['vol_up'] = df['volume'] > df['volume'].shift(1)
      11540 + df['ret'] = df['close'].pct_change()
      11541 + df['pvi_change'] = np.where(df['vol_up'], df['ret'], 0)
      11542 + df['pvi'] = (1 + df['pvi_change']).cumprod() * 1000
      11543 + df['pvi_roc'] = (df['pvi'] - df['pvi'].shift({period})) / df['pvi'].shift({period}) * 100
      11544 + df['fast_rise'] = df['pvi_roc'] > {threshold}
      11545 + df['entry_signal'] = df['fast_rise']""",
      11546 +         params={"period": [20], "threshold": [1, 2]},
      11547 +         direction="long",
      11548 +         lookback=50,
      11549 +         indicators=[],
      11550 +         combinable_with=["momentum", "confirmation"],
      11551 +         strategy_type="PVI",
      11552 +     ),
      11553 + ]
      11554 +
      11555 +
      11556 + # =============================================================================
      11557 + # NEGATIVE VOLUME INDEX BLOCKS
      11558 + # =============================================================================
      11559 +
      11560 + NEGATIVE_VOLUME_BLOCKS = [
      11561 +     # NVI Cross Up
      11562 +     PatternBlock(
      11563 +         id="NVI_CROSS_UP",
      11564 +         name="NVI Cross Up",
      11565 +         category="negative_volume",
      11566 +         formula_template="""df['vol_down'] = df['volume'] < df['volume'].shift(1)
      11567 + df['ret'] = df['close'].pct_change()
      11568 + df['nvi_change'] = np.where(df['vol_down'], df['ret'], 0)
      11569 + df['nvi'] = (1 + df['nvi_change']).cumprod() * 1000
      11570 + df['nvi_ma'] = ta.EMA(df['nvi'], timeperiod={period})
      11571 + df['cross_up'] = (df['nvi'] > df['nvi_ma']) & (df['nvi'].shift(1) <= df['nvi_ma'].shift(1))
      11572 + df['entry_signal'] = df['cross_up']""",
      11573 +         params={"period": [255]},
      11574 +         direction="long",
      11575 +         lookback=270,
      11576 +         indicators=["EMA"],
      11577 +         combinable_with=["momentum", "threshold"],
      11578 +         strategy_type="NVI",
      11579 +     ),
      11580 +     # NVI Above MA
      11581 +     PatternBlock(
      11582 +         id="NVI_ABOVE_MA",
      11583 +         name="NVI Above MA",
      11584 +         category="negative_volume",
      11585 +         formula_template="""df['vol_down'] = df['volume'] < df['volume'].shift(1)
      11586 + df['ret'] = df['close'].pct_change()
      11587 + df['nvi_change'] = np.where(df['vol_down'], df['ret'], 0)
      11588 + df['nvi'] = (1 + df['nvi_change']).cumprod() * 1000
      11589 + df['nvi_ma'] = ta.SMA(df['nvi'], timeperiod={period})
      11590 + df['above'] = df['nvi'] > df['nvi_ma']
      11591 + df['rising'] = df['nvi'] > df['nvi'].shift(5)
      11592 + df['entry_signal'] = df['above'] & df['rising']""",
      11593 +         params={"period": [100, 200]},
      11594 +         direction="long",
      11595 +         lookback=220,
      11596 +         indicators=["SMA"],
      11597 +         combinable_with=["volume", "confirmation"],
      11598 +         strategy_type="NVI",
      11599 +     ),
      11600 +     # NVI Smart Money
      11601 +     PatternBlock(
      11602 +         id="NVI_SMART_MONEY",
      11603 +         name="NVI Smart Money Signal",
      11604 +         category="negative_volume",
      11605 +         formula_template="""df['vol_down'] = df['volume'] < df['volume'].shift(1)
      11606 + df['ret'] = df['close'].pct_change()
      11607 + df['nvi_change'] = np.where(df['vol_down'], df['ret'], 0)
      11608 + df['nvi'] = (1 + df['nvi_change']).cumprod() * 1000
      11609 + df['nvi_trend'] = df['nvi'] > df['nvi'].shift({period})
      11610 + df['price_trend'] = df['close'] > df['close'].shift({period})
      11611 + df['smart'] = df['nvi_trend'] & df['price_trend']
      11612 + df['entry_signal'] = df['smart']""",
      11613 +         params={"period": [20, 50]},
      11614 +         direction="long",
      11615 +         lookback=60,
      11616 +         indicators=[],
      11617 +         combinable_with=["confirmation", "threshold"],
      11618 +         strategy_type="NVI",
      11619 +     ),
      11620 + ]
      11621 +
      11622 +
      11623 + # =============================================================================
      11624 + # INERTIA BLOCKS
      11625 + # =============================================================================
      11626 +
      11627 + INERTIA_BLOCKS = [
      11628 +     # Inertia Rising
      11629 +     PatternBlock(
      11630 +         id="INERTIA_RISING",
      11631 +         name="Inertia Rising",
      11632 +         category="inertia",
      11633 +         formula_template="""df['rvi_num'] = (df['close'] - df['open']) + 2 * (df['close'].shift(1) - df['open'].shift(1)) + 2 *
            +(df['close'].shift(2) - df['open'].shift(2)) + (df['close'].shift(3) - df['open'].shift(3))
      11634 + df['rvi_den'] = (df['high'] - df['low']) + 2 * (df['high'].shift(1) - df['low'].shift(1)) + 2 * (df['high'].shift(2) -
            +df['low'].shift(2)) + (df['high'].shift(3) - df['low'].shift(3))
      11635 + df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
      11636 + df['inertia'] = ta.LINEARREG(df['rvi'], timeperiod={period})
      11637 + df['rising'] = df['inertia'] > df['inertia'].shift(1)
      11638 + df['positive'] = df['inertia'] > 0
      11639 + df['entry_signal'] = df['rising'] & df['positive']""",
      11640 +         params={"period": [14, 20]},
      11641 +         direction="long",
      11642 +         lookback=35,
      11643 +         indicators=["LINEARREG"],
      11644 +         combinable_with=["volume", "momentum"],
      11645 +         strategy_type="INR",
      11646 +     ),
      11647 +     # Inertia Cross Zero
      11648 +     PatternBlock(
      11649 +         id="INERTIA_CROSS_ZERO",
      11650 +         name="Inertia Cross Zero",
      11651 +         category="inertia",
      11652 +         formula_template="""df['rvi_num'] = (df['close'] - df['open']) + 2 * (df['close'].shift(1) - df['open'].shift(1)) + 2 *
            +(df['close'].shift(2) - df['open'].shift(2)) + (df['close'].shift(3) - df['open'].shift(3))
      11653 + df['rvi_den'] = (df['high'] - df['low']) + 2 * (df['high'].shift(1) - df['low'].shift(1)) + 2 * (df['high'].shift(2) -
            +df['low'].shift(2)) + (df['high'].shift(3) - df['low'].shift(3))
      11654 + df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
      11655 + df['inertia'] = ta.LINEARREG(df['rvi'], timeperiod={period})
      11656 + df['cross_up'] = (df['inertia'] > 0) & (df['inertia'].shift(1) <= 0)
      11657 + df['entry_signal'] = df['cross_up']""",
      11658 +         params={"period": [14, 20]},
      11659 +         direction="long",
      11660 +         lookback=35,
      11661 +         indicators=["LINEARREG"],
      11662 +         combinable_with=["confirmation", "threshold"],
      11663 +         strategy_type="INR",
      11664 +     ),
      11665 +     # Inertia Strong
      11666 +     PatternBlock(
      11667 +         id="INERTIA_STRONG",
      11668 +         name="Inertia Strong",
      11669 +         category="inertia",
      11670 +         formula_template="""df['rvi_num'] = (df['close'] - df['open']) + 2 * (df['close'].shift(1) - df['open'].shift(1)) + 2 *
            +(df['close'].shift(2) - df['open'].shift(2)) + (df['close'].shift(3) - df['open'].shift(3))
      11671 + df['rvi_den'] = (df['high'] - df['low']) + 2 * (df['high'].shift(1) - df['low'].shift(1)) + 2 * (df['high'].shift(2) -
            +df['low'].shift(2)) + (df['high'].shift(3) - df['low'].shift(3))
      11672 + df['rvi'] = df['rvi_num'].rolling({period}).sum() / (df['rvi_den'].rolling({period}).sum() + 1e-10)
      11673 + df['inertia'] = ta.LINEARREG(df['rvi'], timeperiod={period})
      11674 + df['strong'] = df['inertia'] > {threshold}
      11675 + df['entry_signal'] = df['strong']""",
      11676 +         params={"period": [14], "threshold": [0.3, 0.4]},
      11677 +         direction="long",
      11678 +         lookback=30,
      11679 +         indicators=["LINEARREG"],
      11680 +         combinable_with=["volume", "confirmation"],
      11681 +         strategy_type="INR",
      11682 +     ),
      11683 + ]
      11684 +
      11685 +
      11686 + # =============================================================================
      11687 + # KNOW SURE THING (KST) BLOCKS
      11688 + # =============================================================================
      11689 +
      11690 + KNOW_SURE_THING_BLOCKS = [
      11691 +     # KST Cross Up
      11692 +     PatternBlock(
      11693 +         id="KST_CROSS_UP",
      11694 +         name="KST Cross Up",
      11695 +         category="know_sure_thing",
      11696 +         formula_template="""df['roc1'] = ta.ROC(df['close'], timeperiod=10)
      11697 + df['roc2'] = ta.ROC(df['close'], timeperiod=15)
      11698 + df['roc3'] = ta.ROC(df['close'], timeperiod=20)
      11699 + df['roc4'] = ta.ROC(df['close'], timeperiod=30)
      11700 + df['kst'] = ta.SMA(df['roc1'], timeperiod=10) * 1 + ta.SMA(df['roc2'], timeperiod=10) * 2 + ta.SMA(df['roc3'], timeperiod=10) * 3
            ++ ta.SMA(df['roc4'], timeperiod=15) * 4
      11701 + df['signal'] = ta.SMA(df['kst'], timeperiod=9)
      11702 + df['cross_up'] = (df['kst'] > df['signal']) & (df['kst'].shift(1) <= df['signal'].shift(1))
      11703 + df['entry_signal'] = df['cross_up']""",
      11704 +         params={},
      11705 +         direction="long",
      11706 +         lookback=50,
      11707 +         indicators=["ROC", "SMA"],
      11708 +         combinable_with=["volume", "momentum"],
      11709 +         strategy_type="KST",
      11710 +     ),
      11711 +     # KST Positive
      11712 +     PatternBlock(
      11713 +         id="KST_POSITIVE",
      11714 +         name="KST Positive Zone",
      11715 +         category="know_sure_thing",
      11716 +         formula_template="""df['roc1'] = ta.ROC(df['close'], timeperiod=10)
      11717 + df['roc2'] = ta.ROC(df['close'], timeperiod=15)
      11718 + df['roc3'] = ta.ROC(df['close'], timeperiod=20)
      11719 + df['roc4'] = ta.ROC(df['close'], timeperiod=30)
      11720 + df['kst'] = ta.SMA(df['roc1'], timeperiod=10) * 1 + ta.SMA(df['roc2'], timeperiod=10) * 2 + ta.SMA(df['roc3'], timeperiod=10) * 3
            ++ ta.SMA(df['roc4'], timeperiod=15) * 4
      11721 + df['positive'] = df['kst'] > 0
      11722 + df['rising'] = df['kst'] > df['kst'].shift(3)
      11723 + df['entry_signal'] = df['positive'] & df['rising']""",
      11724 +         params={},
      11725 +         direction="long",
      11726 +         lookback=50,
      11727 +         indicators=["ROC", "SMA"],
      11728 +         combinable_with=["confirmation", "threshold"],
      11729 +         strategy_type="KST",
      11730 +     ),
      11731 +     # KST Zero Cross
      11732 +     PatternBlock(
      11733 +         id="KST_ZERO_CROSS",
      11734 +         name="KST Zero Cross",
      11735 +         category="know_sure_thing",
      11736 +         formula_template="""df['roc1'] = ta.ROC(df['close'], timeperiod=10)
      11737 + df['roc2'] = ta.ROC(df['close'], timeperiod=15)
      11738 + df['roc3'] = ta.ROC(df['close'], timeperiod=20)
      11739 + df['roc4'] = ta.ROC(df['close'], timeperiod=30)
      11740 + df['kst'] = ta.SMA(df['roc1'], timeperiod=10) * 1 + ta.SMA(df['roc2'], timeperiod=10) * 2 + ta.SMA(df['roc3'], timeperiod=10) * 3
            ++ ta.SMA(df['roc4'], timeperiod=15) * 4
      11741 + df['cross_zero'] = (df['kst'] > 0) & (df['kst'].shift(1) <= 0)
      11742 + df['entry_signal'] = df['cross_zero']""",
      11743 +         params={},
      11744 +         direction="long",
      11745 +         lookback=50,
      11746 +         indicators=["ROC", "SMA"],
      11747 +         combinable_with=["volume", "confirmation"],
      11748 +         strategy_type="KST",
      11749 +     ),
      11750 + ]
      11751 +
      11752 +
      11753 + # =============================================================================
      11754 + # SPECIAL K BLOCKS
      11755 + # =============================================================================
      11756 +
      11757 + SPECIAL_K_BLOCKS = [
      11758 +     # Special K Rising
      11759 +     PatternBlock(
      11760 +         id="SPECIAL_K_RISING",
      11761 +         name="Special K Rising",
      11762 +         category="special_k",
      11763 +         formula_template="""df['roc10'] = ta.ROC(df['close'], timeperiod=10)
      11764 + df['roc15'] = ta.ROC(df['close'], timeperiod=15)
      11765 + df['roc20'] = ta.ROC(df['close'], timeperiod=20)
      11766 + df['roc30'] = ta.ROC(df['close'], timeperiod=30)
      11767 + df['roc40'] = ta.ROC(df['close'], timeperiod=40)
      11768 + df['roc65'] = ta.ROC(df['close'], timeperiod=65)
      11769 + df['spk'] = ta.SMA(df['roc10'], timeperiod=10) + ta.SMA(df['roc15'], timeperiod=10) * 2 + ta.SMA(df['roc20'], timeperiod=10) * 3 +
            + ta.SMA(df['roc30'], timeperiod=15) * 4 + ta.SMA(df['roc40'], timeperiod=50) + ta.SMA(df['roc65'], timeperiod=65) * 2
      11770 + df['rising'] = df['spk'] > df['spk'].shift(3)
      11771 + df['positive'] = df['spk'] > 0
      11772 + df['entry_signal'] = df['rising'] & df['positive']""",
      11773 +         params={},
      11774 +         direction="long",
      11775 +         lookback=150,
      11776 +         indicators=["ROC", "SMA"],
      11777 +         combinable_with=["momentum", "confirmation"],
      11778 +         strategy_type="SPK",
      11779 +     ),
      11780 +     # Special K Cross Zero
      11781 +     PatternBlock(
      11782 +         id="SPECIAL_K_ZERO_CROSS",
      11783 +         name="Special K Zero Cross",
      11784 +         category="special_k",
      11785 +         formula_template="""df['roc10'] = ta.ROC(df['close'], timeperiod=10)
      11786 + df['roc15'] = ta.ROC(df['close'], timeperiod=15)
      11787 + df['roc20'] = ta.ROC(df['close'], timeperiod=20)
      11788 + df['roc30'] = ta.ROC(df['close'], timeperiod=30)
      11789 + df['roc40'] = ta.ROC(df['close'], timeperiod=40)
      11790 + df['roc65'] = ta.ROC(df['close'], timeperiod=65)
      11791 + df['spk'] = ta.SMA(df['roc10'], timeperiod=10) + ta.SMA(df['roc15'], timeperiod=10) * 2 + ta.SMA(df['roc20'], timeperiod=10) * 3 +
            + ta.SMA(df['roc30'], timeperiod=15) * 4 + ta.SMA(df['roc40'], timeperiod=50) + ta.SMA(df['roc65'], timeperiod=65) * 2
      11792 + df['cross_zero'] = (df['spk'] > 0) & (df['spk'].shift(1) <= 0)
      11793 + df['entry_signal'] = df['cross_zero']""",
      11794 +         params={},
      11795 +         direction="long",
      11796 +         lookback=150,
      11797 +         indicators=["ROC", "SMA"],
      11798 +         combinable_with=["volume", "threshold"],
      11799 +         strategy_type="SPK",
      11800 +     ),
      11801 +     # Special K Momentum
      11802 +     PatternBlock(
      11803 +         id="SPECIAL_K_MOMENTUM",
      11804 +         name="Special K Momentum",
      11805 +         category="special_k",
      11806 +         formula_template="""df['roc10'] = ta.ROC(df['close'], timeperiod=10)
      11807 + df['roc15'] = ta.ROC(df['close'], timeperiod=15)
      11808 + df['roc20'] = ta.ROC(df['close'], timeperiod=20)
      11809 + df['roc30'] = ta.ROC(df['close'], timeperiod=30)
      11810 + df['roc40'] = ta.ROC(df['close'], timeperiod=40)
      11811 + df['roc65'] = ta.ROC(df['close'], timeperiod=65)
      11812 + df['spk'] = ta.SMA(df['roc10'], timeperiod=10) + ta.SMA(df['roc15'], timeperiod=10) * 2 + ta.SMA(df['roc20'], timeperiod=10) * 3 +
            + ta.SMA(df['roc30'], timeperiod=15) * 4 + ta.SMA(df['roc40'], timeperiod=50) + ta.SMA(df['roc65'], timeperiod=65) * 2
      11813 + df['spk_mom'] = df['spk'] - df['spk'].shift(5)
      11814 + df['strong_mom'] = df['spk_mom'] > df['spk_mom'].rolling(20).std()
      11815 + df['entry_signal'] = df['strong_mom']""",
      11816 +         params={},
      11817 +         direction="long",
      11818 +         lookback=150,
      11819 +         indicators=["ROC", "SMA"],
      11820 +         combinable_with=["confirmation", "volume"],
      11821 +         strategy_type="SPK",
      11822 +     ),
      11823 + ]
      11824 +
      11825 +
      11826 + # =============================================================================
      11827   # ALL BLOCKS COMBINED
      11828   # =============================================================================
      11829

● Ora aggiorno ALL_BLOCKS.

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      11982       + MCGINLEY_BLOCKS
      11983       + T3_MA_BLOCKS
      11984       + JURIK_MA_BLOCKS
      11985 +     + ZERO_LAG_MA_BLOCKS
      11986 +     + HULL_MA_BLOCKS
      11987 +     + LAGUERRE_BLOCKS
      11988 +     + STOCHASTIC_EXT_BLOCKS
      11989 +     + WILLIAMS_AD_BLOCKS
      11990 +     + POSITIVE_VOLUME_BLOCKS
      11991 +     + NEGATIVE_VOLUME_BLOCKS
      11992 +     + INERTIA_BLOCKS
      11993 +     + KNOW_SURE_THING_BLOCKS
      11994 +     + SPECIAL_K_BLOCKS
      11995   )
      11996
      11997   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python -c "
      from src.generator.pattern_gen.building_blocks import ALL_BLOCKS, BLOCKS_BY_CATEGORY…)
  ⎿  Total blocks: 598
     Categories: 163
     … +27 lines (ctrl+o to expand)

● Round 16 completato!

  Risultati:
  - Blocchi totali: 598 (da 568, +30)
  - Categorie: 163 (da 153, +10)
  - Validazione: 200/200 OK
  - Lookahead: 2 falsi positivi (.iloc[0] per accesso a costanti, non dati futuri)
  - Strategie stimate: ~122,784

  ---
  Altre possibili migliorie (Round 17)?

  Potrei aggiungere altri ~30 blocchi:

  1. PERCENTAGE_PRICE_OSC_BLOCKS (3) - PPO extended patterns
  2. ABSOLUTE_PRICE_OSC_BLOCKS (3) - APO signals
  3. DETRENDED_VOLUME_BLOCKS (3) - Volume detrending
  4. RELATIVE_MOMENTUM_BLOCKS (3) - RMI indicator
  5. STOCHASTIC_MOMENTUM_BLOCKS (3) - SMI oscillator
  6. PROJECTION_OSC_BLOCKS (3) - Projection oscillator
  7. PROJECTION_BANDS_BLOCKS (3) - Projection bands
  8. PRICE_MOMENTUM_OSC_BLOCKS (3) - PMO signals
  9. DECISION_POINT_BLOCKS (3) - DecisionPoint indicators
  10. VOLUME_WEIGHTED_RSI_BLOCKS (3) - Volume-weighted RSI

  Totale: +30 blocchi → 628 blocchi, ~130,000+ strategie

  Vuoi che implementi?

✻ Cooked for 2m 48s

❯ si

● Search(pattern: "SPECIAL_K_BLOCKS = \[", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 60 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 630 lines
      11824
      11825
      11826   # =============================================================================
      11827 + # PERCENTAGE PRICE OSCILLATOR EXTENDED BLOCKS
      11828 + # =============================================================================
      11829 +
      11830 + PERCENTAGE_PRICE_OSC_BLOCKS = [
      11831 +     # PPO Cross Up
      11832 +     PatternBlock(
      11833 +         id="PPO_CROSS_UP_EXT",
      11834 +         name="PPO Cross Up Extended",
      11835 +         category="percentage_price_osc",
      11836 +         formula_template="""df['ppo'] = ta.PPO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
      11837 + df['ppo_signal'] = ta.EMA(df['ppo'], timeperiod=9)
      11838 + df['cross_up'] = (df['ppo'] > df['ppo_signal']) & (df['ppo'].shift(1) <= df['ppo_signal'].shift(1))
      11839 + df['entry_signal'] = df['cross_up']""",
      11840 +         params={"fast": [12], "slow": [26]},
      11841 +         direction="long",
      11842 +         lookback=40,
      11843 +         indicators=["PPO", "EMA"],
      11844 +         combinable_with=["volume", "momentum"],
      11845 +         strategy_type="PPX",
      11846 +     ),
      11847 +     # PPO Histogram Rising
      11848 +     PatternBlock(
      11849 +         id="PPO_HIST_RISING",
      11850 +         name="PPO Histogram Rising",
      11851 +         category="percentage_price_osc",
      11852 +         formula_template="""df['ppo'] = ta.PPO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
      11853 + df['ppo_signal'] = ta.EMA(df['ppo'], timeperiod=9)
      11854 + df['ppo_hist'] = df['ppo'] - df['ppo_signal']
      11855 + df['hist_rising'] = df['ppo_hist'] > df['ppo_hist'].shift(1)
      11856 + df['hist_rising_count'] = df['hist_rising'].rolling(3).sum() >= 2
      11857 + df['entry_signal'] = df['hist_rising_count']""",
      11858 +         params={"fast": [12], "slow": [26]},
      11859 +         direction="long",
      11860 +         lookback=40,
      11861 +         indicators=["PPO", "EMA"],
      11862 +         combinable_with=["confirmation", "threshold"],
      11863 +         strategy_type="PPX",
      11864 +     ),
      11865 +     # PPO Zero Cross
      11866 +     PatternBlock(
      11867 +         id="PPO_ZERO_CROSS_EXT",
      11868 +         name="PPO Zero Cross Extended",
      11869 +         category="percentage_price_osc",
      11870 +         formula_template="""df['ppo'] = ta.PPO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
      11871 + df['cross_zero'] = (df['ppo'] > 0) & (df['ppo'].shift(1) <= 0)
      11872 + df['ppo_rising'] = df['ppo'] > df['ppo'].shift(3)
      11873 + df['entry_signal'] = df['cross_zero'] & df['ppo_rising']""",
      11874 +         params={"fast": [12], "slow": [26]},
      11875 +         direction="long",
      11876 +         lookback=40,
      11877 +         indicators=["PPO"],
      11878 +         combinable_with=["volume", "confirmation"],
      11879 +         strategy_type="PPX",
      11880 +     ),
      11881 + ]
      11882 +
      11883 +
      11884 + # =============================================================================
      11885 + # ABSOLUTE PRICE OSCILLATOR BLOCKS
      11886 + # =============================================================================
      11887 +
      11888 + ABSOLUTE_PRICE_OSC_BLOCKS = [
      11889 +     # APO Cross Up
      11890 +     PatternBlock(
      11891 +         id="APO_CROSS_UP",
      11892 +         name="APO Cross Up",
      11893 +         category="absolute_price_osc",
      11894 +         formula_template="""df['apo'] = ta.APO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
      11895 + df['apo_signal'] = ta.EMA(df['apo'], timeperiod=9)
      11896 + df['cross_up'] = (df['apo'] > df['apo_signal']) & (df['apo'].shift(1) <= df['apo_signal'].shift(1))
      11897 + df['entry_signal'] = df['cross_up']""",
      11898 +         params={"fast": [12], "slow": [26]},
      11899 +         direction="long",
      11900 +         lookback=40,
      11901 +         indicators=["APO", "EMA"],
      11902 +         combinable_with=["volume", "momentum"],
      11903 +         strategy_type="APO",
      11904 +     ),
      11905 +     # APO Zero Cross
      11906 +     PatternBlock(
      11907 +         id="APO_ZERO_CROSS",
      11908 +         name="APO Zero Cross",
      11909 +         category="absolute_price_osc",
      11910 +         formula_template="""df['apo'] = ta.APO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
      11911 + df['cross_zero'] = (df['apo'] > 0) & (df['apo'].shift(1) <= 0)
      11912 + df['entry_signal'] = df['cross_zero']""",
      11913 +         params={"fast": [12], "slow": [26]},
      11914 +         direction="long",
      11915 +         lookback=40,
      11916 +         indicators=["APO"],
      11917 +         combinable_with=["confirmation", "threshold"],
      11918 +         strategy_type="APO",
      11919 +     ),
      11920 +     # APO Positive Rising
      11921 +     PatternBlock(
      11922 +         id="APO_POSITIVE_RISING",
      11923 +         name="APO Positive Rising",
      11924 +         category="absolute_price_osc",
      11925 +         formula_template="""df['apo'] = ta.APO(df['close'], fastperiod={fast}, slowperiod={slow}, matype=1)
      11926 + df['positive'] = df['apo'] > 0
      11927 + df['rising'] = df['apo'] > df['apo'].shift(3)
      11928 + df['entry_signal'] = df['positive'] & df['rising']""",
      11929 +         params={"fast": [12], "slow": [26]},
      11930 +         direction="long",
      11931 +         lookback=40,
      11932 +         indicators=["APO"],
      11933 +         combinable_with=["volume", "confirmation"],
      11934 +         strategy_type="APO",
      11935 +     ),
      11936 + ]
      11937 +
      11938 +
      11939 + # =============================================================================
      11940 + # DETRENDED VOLUME BLOCKS
      11941 + # =============================================================================
      11942 +
      11943 + DETRENDED_VOLUME_BLOCKS = [
      11944 +     # Volume Above Trend
      11945 +     PatternBlock(
      11946 +         id="VOL_ABOVE_TREND",
      11947 +         name="Volume Above Trend",
      11948 +         category="detrended_volume",
      11949 +         formula_template="""df['vol_ma'] = ta.SMA(df['volume'], timeperiod={period})
      11950 + df['vol_trend'] = ta.LINEARREG(df['volume'], timeperiod={period})
      11951 + df['above_trend'] = df['volume'] > df['vol_trend'] * {mult}
      11952 + df['price_up'] = df['close'] > df['close'].shift(1)
      11953 + df['entry_signal'] = df['above_trend'] & df['price_up']""",
      11954 +         params={"period": [20], "mult": [1.2, 1.5]},
      11955 +         direction="long",
      11956 +         lookback=30,
      11957 +         indicators=["SMA", "LINEARREG"],
      11958 +         combinable_with=["momentum", "threshold"],
      11959 +         strategy_type="DTV",
      11960 +     ),
      11961 +     # Volume Breakout
      11962 +     PatternBlock(
      11963 +         id="VOL_BREAKOUT_DT",
      11964 +         name="Volume Detrended Breakout",
      11965 +         category="detrended_volume",
      11966 +         formula_template="""df['vol_ma'] = ta.SMA(df['volume'], timeperiod={period})
      11967 + df['vol_detrend'] = df['volume'] - df['vol_ma']
      11968 + df['vol_std'] = df['vol_detrend'].rolling({period}).std()
      11969 + df['breakout'] = df['vol_detrend'] > df['vol_std'] * {mult}
      11970 + df['entry_signal'] = df['breakout']""",
      11971 +         params={"period": [20], "mult": [2.0, 2.5]},
      11972 +         direction="bidi",
      11973 +         lookback=30,
      11974 +         indicators=["SMA"],
      11975 +         combinable_with=["momentum", "confirmation"],
      11976 +         strategy_type="DTV",
      11977 +     ),
      11978 +     # Volume Mean Reversion
      11979 +     PatternBlock(
      11980 +         id="VOL_MEAN_REV",
      11981 +         name="Volume Mean Reversion",
      11982 +         category="detrended_volume",
      11983 +         formula_template="""df['vol_ma'] = ta.SMA(df['volume'], timeperiod={period})
      11984 + df['vol_detrend'] = df['volume'] - df['vol_ma']
      11985 + df['was_low'] = df['vol_detrend'].shift(1) < 0
      11986 + df['now_rising'] = df['vol_detrend'] > df['vol_detrend'].shift(1)
      11987 + df['price_up'] = df['close'] > df['open']
      11988 + df['entry_signal'] = df['was_low'] & df['now_rising'] & df['price_up']""",
      11989 +         params={"period": [20, 30]},
      11990 +         direction="long",
      11991 +         lookback=35,
      11992 +         indicators=["SMA"],
      11993 +         combinable_with=["volume", "confirmation"],
      11994 +         strategy_type="DTV",
      11995 +     ),
      11996 + ]
      11997 +
      11998 +
      11999 + # =============================================================================
      12000 + # RELATIVE MOMENTUM INDEX BLOCKS
      12001 + # =============================================================================
      12002 +
      12003 + RELATIVE_MOMENTUM_BLOCKS = [
      12004 +     # RMI Oversold
      12005 +     PatternBlock(
      12006 +         id="RMI_OVERSOLD",
      12007 +         name="RMI Oversold",
      12008 +         category="relative_momentum",
      12009 +         formula_template="""df['delta'] = df['close'] - df['close'].shift({momentum})
      12010 + df['up'] = np.where(df['delta'] > 0, df['delta'], 0)
      12011 + df['down'] = np.where(df['delta'] < 0, -df['delta'], 0)
      12012 + df['up_avg'] = ta.EMA(df['up'], timeperiod={period})
      12013 + df['down_avg'] = ta.EMA(df['down'], timeperiod={period})
      12014 + df['rmi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
      12015 + df['oversold'] = df['rmi'] < {level}
      12016 + df['entry_signal'] = df['oversold']""",
      12017 +         params={"period": [14], "momentum": [4], "level": [30, 35]},
      12018 +         direction="long",
      12019 +         lookback=30,
      12020 +         indicators=["EMA"],
      12021 +         combinable_with=["volume", "confirmation"],
      12022 +         strategy_type="RMI",
      12023 +     ),
      12024 +     # RMI Cross Up
      12025 +     PatternBlock(
      12026 +         id="RMI_CROSS_UP",
      12027 +         name="RMI Cross Up",
      12028 +         category="relative_momentum",
      12029 +         formula_template="""df['delta'] = df['close'] - df['close'].shift({momentum})
      12030 + df['up'] = np.where(df['delta'] > 0, df['delta'], 0)
      12031 + df['down'] = np.where(df['delta'] < 0, -df['delta'], 0)
      12032 + df['up_avg'] = ta.EMA(df['up'], timeperiod={period})
      12033 + df['down_avg'] = ta.EMA(df['down'], timeperiod={period})
      12034 + df['rmi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
      12035 + df['cross_up'] = (df['rmi'] > 50) & (df['rmi'].shift(1) <= 50)
      12036 + df['entry_signal'] = df['cross_up']""",
      12037 +         params={"period": [14], "momentum": [4]},
      12038 +         direction="long",
      12039 +         lookback=30,
      12040 +         indicators=["EMA"],
      12041 +         combinable_with=["momentum", "threshold"],
      12042 +         strategy_type="RMI",
      12043 +     ),
      12044 +     # RMI Strong
      12045 +     PatternBlock(
      12046 +         id="RMI_STRONG",
      12047 +         name="RMI Strong",
      12048 +         category="relative_momentum",
      12049 +         formula_template="""df['delta'] = df['close'] - df['close'].shift({momentum})
      12050 + df['up'] = np.where(df['delta'] > 0, df['delta'], 0)
      12051 + df['down'] = np.where(df['delta'] < 0, -df['delta'], 0)
      12052 + df['up_avg'] = ta.EMA(df['up'], timeperiod={period})
      12053 + df['down_avg'] = ta.EMA(df['down'], timeperiod={period})
      12054 + df['rmi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
      12055 + df['strong'] = df['rmi'] > {level}
      12056 + df['rising'] = df['rmi'] > df['rmi'].shift(3)
      12057 + df['entry_signal'] = df['strong'] & df['rising']""",
      12058 +         params={"period": [14], "momentum": [4], "level": [60, 65]},
      12059 +         direction="long",
      12060 +         lookback=30,
      12061 +         indicators=["EMA"],
      12062 +         combinable_with=["volume", "confirmation"],
      12063 +         strategy_type="RMI",
      12064 +     ),
      12065 + ]
      12066 +
      12067 +
      12068 + # =============================================================================
      12069 + # STOCHASTIC MOMENTUM INDEX BLOCKS
      12070 + # =============================================================================
      12071 +
      12072 + STOCHASTIC_MOMENTUM_BLOCKS = [
      12073 +     # SMI Oversold
      12074 +     PatternBlock(
      12075 +         id="SMI_OVERSOLD",
      12076 +         name="SMI Oversold",
      12077 +         category="stochastic_momentum",
      12078 +         formula_template="""df['hh'] = df['high'].rolling({period}).max()
      12079 + df['ll'] = df['low'].rolling({period}).min()
      12080 + df['mid'] = (df['hh'] + df['ll']) / 2
      12081 + df['d'] = df['close'] - df['mid']
      12082 + df['hl'] = df['hh'] - df['ll']
      12083 + df['d_smooth'] = ta.EMA(ta.EMA(df['d'], timeperiod={smooth}), timeperiod={smooth})
      12084 + df['hl_smooth'] = ta.EMA(ta.EMA(df['hl'], timeperiod={smooth}), timeperiod={smooth})
      12085 + df['smi'] = 100 * df['d_smooth'] / (df['hl_smooth'] / 2 + 1e-10)
      12086 + df['oversold'] = df['smi'] < {level}
      12087 + df['entry_signal'] = df['oversold']""",
      12088 +         params={"period": [13], "smooth": [5], "level": [-40, -45]},
      12089 +         direction="long",
      12090 +         lookback=35,
      12091 +         indicators=["EMA"],
      12092 +         combinable_with=["volume", "confirmation"],
      12093 +         strategy_type="SMI",
      12094 +     ),
      12095 +     # SMI Cross Up
      12096 +     PatternBlock(
      12097 +         id="SMI_CROSS_UP",
      12098 +         name="SMI Cross Up",
      12099 +         category="stochastic_momentum",
      12100 +         formula_template="""df['hh'] = df['high'].rolling({period}).max()
      12101 + df['ll'] = df['low'].rolling({period}).min()
      12102 + df['mid'] = (df['hh'] + df['ll']) / 2
      12103 + df['d'] = df['close'] - df['mid']
      12104 + df['hl'] = df['hh'] - df['ll']
      12105 + df['d_smooth'] = ta.EMA(ta.EMA(df['d'], timeperiod={smooth}), timeperiod={smooth})
      12106 + df['hl_smooth'] = ta.EMA(ta.EMA(df['hl'], timeperiod={smooth}), timeperiod={smooth})
      12107 + df['smi'] = 100 * df['d_smooth'] / (df['hl_smooth'] / 2 + 1e-10)
      12108 + df['signal'] = ta.EMA(df['smi'], timeperiod=3)
      12109 + df['cross_up'] = (df['smi'] > df['signal']) & (df['smi'].shift(1) <= df['signal'].shift(1))
      12110 + df['entry_signal'] = df['cross_up']""",
      12111 +         params={"period": [13], "smooth": [5]},
      12112 +         direction="long",
      12113 +         lookback=35,
      12114 +         indicators=["EMA"],
      12115 +         combinable_with=["momentum", "threshold"],
      12116 +         strategy_type="SMI",
      12117 +     ),
      12118 +     # SMI Zero Cross
      12119 +     PatternBlock(
      12120 +         id="SMI_ZERO_CROSS",
      12121 +         name="SMI Zero Cross",
      12122 +         category="stochastic_momentum",
      12123 +         formula_template="""df['hh'] = df['high'].rolling({period}).max()
      12124 + df['ll'] = df['low'].rolling({period}).min()
      12125 + df['mid'] = (df['hh'] + df['ll']) / 2
      12126 + df['d'] = df['close'] - df['mid']
      12127 + df['hl'] = df['hh'] - df['ll']
      12128 + df['d_smooth'] = ta.EMA(ta.EMA(df['d'], timeperiod={smooth}), timeperiod={smooth})
      12129 + df['hl_smooth'] = ta.EMA(ta.EMA(df['hl'], timeperiod={smooth}), timeperiod={smooth})
      12130 + df['smi'] = 100 * df['d_smooth'] / (df['hl_smooth'] / 2 + 1e-10)
      12131 + df['cross_zero'] = (df['smi'] > 0) & (df['smi'].shift(1) <= 0)
      12132 + df['entry_signal'] = df['cross_zero']""",
      12133 +         params={"period": [13], "smooth": [5]},
      12134 +         direction="long",
      12135 +         lookback=35,
      12136 +         indicators=["EMA"],
      12137 +         combinable_with=["volume", "confirmation"],
      12138 +         strategy_type="SMI",
      12139 +     ),
      12140 + ]
      12141 +
      12142 +
      12143 + # =============================================================================
      12144 + # PROJECTION OSCILLATOR BLOCKS
      12145 + # =============================================================================
      12146 +
      12147 + PROJECTION_OSC_BLOCKS = [
      12148 +     # Projection Oscillator Oversold
      12149 +     PatternBlock(
      12150 +         id="PROJ_OSC_OVERSOLD",
      12151 +         name="Projection Oscillator Oversold",
      12152 +         category="projection_osc",
      12153 +         formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
      12154 + df['upper'] = ta.LINEARREG(df['high'], timeperiod={period}) + df['slope'] * {period}
      12155 + df['lower'] = ta.LINEARREG(df['low'], timeperiod={period}) + df['slope'] * {period}
      12156 + df['proj_osc'] = 100 * (df['close'] - df['lower']) / (df['upper'] - df['lower'] + 1e-10)
      12157 + df['oversold'] = df['proj_osc'] < {level}
      12158 + df['entry_signal'] = df['oversold']""",
      12159 +         params={"period": [14], "level": [20, 25]},
      12160 +         direction="long",
      12161 +         lookback=25,
      12162 +         indicators=["LINEARREG_SLOPE", "LINEARREG"],
      12163 +         combinable_with=["volume", "confirmation"],
      12164 +         strategy_type="PRO",
      12165 +     ),
      12166 +     # Projection Oscillator Rising
      12167 +     PatternBlock(
      12168 +         id="PROJ_OSC_RISING",
      12169 +         name="Projection Oscillator Rising",
      12170 +         category="projection_osc",
      12171 +         formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
      12172 + df['upper'] = ta.LINEARREG(df['high'], timeperiod={period}) + df['slope'] * {period}
      12173 + df['lower'] = ta.LINEARREG(df['low'], timeperiod={period}) + df['slope'] * {period}
      12174 + df['proj_osc'] = 100 * (df['close'] - df['lower']) / (df['upper'] - df['lower'] + 1e-10)
      12175 + df['rising'] = df['proj_osc'] > df['proj_osc'].shift(3)
      12176 + df['above_mid'] = df['proj_osc'] > 50
      12177 + df['entry_signal'] = df['rising'] & df['above_mid']""",
      12178 +         params={"period": [14]},
      12179 +         direction="long",
      12180 +         lookback=25,
      12181 +         indicators=["LINEARREG_SLOPE", "LINEARREG"],
      12182 +         combinable_with=["momentum", "threshold"],
      12183 +         strategy_type="PRO",
      12184 +     ),
      12185 +     # Projection Oscillator Cross
      12186 +     PatternBlock(
      12187 +         id="PROJ_OSC_CROSS",
      12188 +         name="Projection Oscillator Cross",
      12189 +         category="projection_osc",
      12190 +         formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
      12191 + df['upper'] = ta.LINEARREG(df['high'], timeperiod={period}) + df['slope'] * {period}
      12192 + df['lower'] = ta.LINEARREG(df['low'], timeperiod={period}) + df['slope'] * {period}
      12193 + df['proj_osc'] = 100 * (df['close'] - df['lower']) / (df['upper'] - df['lower'] + 1e-10)
      12194 + df['cross_up'] = (df['proj_osc'] > 50) & (df['proj_osc'].shift(1) <= 50)
      12195 + df['entry_signal'] = df['cross_up']""",
      12196 +         params={"period": [14]},
      12197 +         direction="long",
      12198 +         lookback=25,
      12199 +         indicators=["LINEARREG_SLOPE", "LINEARREG"],
      12200 +         combinable_with=["volume", "confirmation"],
      12201 +         strategy_type="PRO",
      12202 +     ),
      12203 + ]
      12204 +
      12205 +
      12206 + # =============================================================================
      12207 + # PROJECTION BANDS BLOCKS
      12208 + # =============================================================================
      12209 +
      12210 + PROJECTION_BANDS_BLOCKS = [
      12211 +     # Projection Bands Lower Touch
      12212 +     PatternBlock(
      12213 +         id="PROJ_BANDS_LOWER",
      12214 +         name="Projection Bands Lower Touch",
      12215 +         category="projection_bands",
      12216 +         formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
      12217 + df['reg'] = ta.LINEARREG(df['close'], timeperiod={period})
      12218 + df['upper'] = ta.MAX(df['high'] - df['reg'], timeperiod={period}) + df['reg']
      12219 + df['lower'] = df['reg'] - ta.MAX(df['reg'] - df['low'], timeperiod={period})
      12220 + df['at_lower'] = df['low'] <= df['lower'] * 1.01
      12221 + df['bounce'] = df['close'] > df['open']
      12222 + df['entry_signal'] = df['at_lower'] & df['bounce']""",
      12223 +         params={"period": [14]},
      12224 +         direction="long",
      12225 +         lookback=25,
      12226 +         indicators=["LINEARREG_SLOPE", "LINEARREG", "MAX"],
      12227 +         combinable_with=["volume", "confirmation"],
      12228 +         strategy_type="PRB",
      12229 +     ),
      12230 +     # Projection Bands Breakout
      12231 +     PatternBlock(
      12232 +         id="PROJ_BANDS_BREAKOUT",
      12233 +         name="Projection Bands Breakout",
      12234 +         category="projection_bands",
      12235 +         formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
      12236 + df['reg'] = ta.LINEARREG(df['close'], timeperiod={period})
      12237 + df['upper'] = ta.MAX(df['high'] - df['reg'], timeperiod={period}) + df['reg']
      12238 + df['breakout'] = (df['close'] > df['upper']) & (df['close'].shift(1) <= df['upper'].shift(1))
      12239 + df['entry_signal'] = df['breakout']""",
      12240 +         params={"period": [14, 20]},
      12241 +         direction="long",
      12242 +         lookback=30,
      12243 +         indicators=["LINEARREG_SLOPE", "LINEARREG", "MAX"],
      12244 +         combinable_with=["momentum", "threshold"],
      12245 +         strategy_type="PRB",
      12246 +     ),
      12247 +     # Projection Bands Mid Cross
      12248 +     PatternBlock(
      12249 +         id="PROJ_BANDS_MID",
      12250 +         name="Projection Bands Mid Cross",
      12251 +         category="projection_bands",
      12252 +         formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
      12253 + df['reg'] = ta.LINEARREG(df['close'], timeperiod={period})
      12254 + df['cross_up'] = (df['close'] > df['reg']) & (df['close'].shift(1) <= df['reg'].shift(1))
      12255 + df['slope_pos'] = df['slope'] > 0
      12256 + df['entry_signal'] = df['cross_up'] & df['slope_pos']""",
      12257 +         params={"period": [14]},
      12258 +         direction="long",
      12259 +         lookback=25,
      12260 +         indicators=["LINEARREG_SLOPE", "LINEARREG"],
      12261 +         combinable_with=["volume", "confirmation"],
      12262 +         strategy_type="PRB",
      12263 +     ),
      12264 + ]
      12265 +
      12266 +
      12267 + # =============================================================================
      12268 + # PRICE MOMENTUM OSCILLATOR BLOCKS
      12269 + # =============================================================================
      12270 +
      12271 + PRICE_MOMENTUM_OSC_BLOCKS = [
      12272 +     # PMO Cross Up
      12273 +     PatternBlock(
      12274 +         id="PMO_CROSS_UP",
      12275 +         name="PMO Cross Up",
      12276 +         category="price_momentum_osc",
      12277 +         formula_template="""df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
      12278 + df['roc_ema1'] = ta.EMA(df['roc'], timeperiod={smooth1})
      12279 + df['pmo'] = ta.EMA(df['roc_ema1'] * 10, timeperiod={smooth2})
      12280 + df['signal'] = ta.EMA(df['pmo'], timeperiod=10)
      12281 + df['cross_up'] = (df['pmo'] > df['signal']) & (df['pmo'].shift(1) <= df['signal'].shift(1))
      12282 + df['entry_signal'] = df['cross_up']""",
      12283 +         params={"smooth1": [35], "smooth2": [20]},
      12284 +         direction="long",
      12285 +         lookback=60,
      12286 +         indicators=["EMA"],
      12287 +         combinable_with=["volume", "momentum"],
      12288 +         strategy_type="PMO",
      12289 +     ),
      12290 +     # PMO Zero Cross
      12291 +     PatternBlock(
      12292 +         id="PMO_ZERO_CROSS",
      12293 +         name="PMO Zero Cross",
      12294 +         category="price_momentum_osc",
      12295 +         formula_template="""df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
      12296 + df['roc_ema1'] = ta.EMA(df['roc'], timeperiod={smooth1})
      12297 + df['pmo'] = ta.EMA(df['roc_ema1'] * 10, timeperiod={smooth2})
      12298 + df['cross_zero'] = (df['pmo'] > 0) & (df['pmo'].shift(1) <= 0)
      12299 + df['entry_signal'] = df['cross_zero']""",
      12300 +         params={"smooth1": [35], "smooth2": [20]},
      12301 +         direction="long",
      12302 +         lookback=60,
      12303 +         indicators=["EMA"],
      12304 +         combinable_with=["confirmation", "threshold"],
      12305 +         strategy_type="PMO",
      12306 +     ),
      12307 +     # PMO Rising Strong
      12308 +     PatternBlock(
      12309 +         id="PMO_RISING_STRONG",
      12310 +         name="PMO Rising Strong",
      12311 +         category="price_momentum_osc",
      12312 +         formula_template="""df['roc'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1) * 100
      12313 + df['roc_ema1'] = ta.EMA(df['roc'], timeperiod={smooth1})
      12314 + df['pmo'] = ta.EMA(df['roc_ema1'] * 10, timeperiod={smooth2})
      12315 + df['signal'] = ta.EMA(df['pmo'], timeperiod=10)
      12316 + df['rising'] = df['pmo'] > df['pmo'].shift(3)
      12317 + df['above_signal'] = df['pmo'] > df['signal']
      12318 + df['entry_signal'] = df['rising'] & df['above_signal']""",
      12319 +         params={"smooth1": [35], "smooth2": [20]},
      12320 +         direction="long",
      12321 +         lookback=60,
      12322 +         indicators=["EMA"],
      12323 +         combinable_with=["volume", "confirmation"],
      12324 +         strategy_type="PMO",
      12325 +     ),
      12326 + ]
      12327 +
      12328 +
      12329 + # =============================================================================
      12330 + # DECISION POINT BLOCKS
      12331 + # =============================================================================
      12332 +
      12333 + DECISION_POINT_BLOCKS = [
      12334 +     # Decision Point Breadth
      12335 +     PatternBlock(
      12336 +         id="DP_BREADTH",
      12337 +         name="Decision Point Breadth Proxy",
      12338 +         category="decision_point",
      12339 +         formula_template="""df['up_day'] = df['close'] > df['close'].shift(1)
      12340 + df['breadth'] = df['up_day'].rolling({period}).sum() / {period} * 100
      12341 + df['breadth_ma'] = ta.EMA(df['breadth'], timeperiod={ma_period})
      12342 + df['cross_up'] = (df['breadth'] > df['breadth_ma']) & (df['breadth'].shift(1) <= df['breadth_ma'].shift(1))
      12343 + df['entry_signal'] = df['cross_up']""",
      12344 +         params={"period": [20], "ma_period": [10]},
      12345 +         direction="long",
      12346 +         lookback=40,
      12347 +         indicators=["EMA"],
      12348 +         combinable_with=["volume", "momentum"],
      12349 +         strategy_type="DPT",
      12350 +     ),
      12351 +     # Decision Point Thrust
      12352 +     PatternBlock(
      12353 +         id="DP_THRUST",
      12354 +         name="Decision Point Thrust",
      12355 +         category="decision_point",
      12356 +         formula_template="""df['up_day'] = df['close'] > df['close'].shift(1)
      12357 + df['breadth'] = df['up_day'].rolling({period}).sum() / {period} * 100
      12358 + df['thrust'] = df['breadth'] > {threshold}
      12359 + df['entry_signal'] = df['thrust']""",
      12360 +         params={"period": [10], "threshold": [70, 80]},
      12361 +         direction="long",
      12362 +         lookback=20,
      12363 +         indicators=[],
      12364 +         combinable_with=["confirmation", "threshold"],
      12365 +         strategy_type="DPT",
      12366 +     ),
      12367 +     # Decision Point Rising
      12368 +     PatternBlock(
      12369 +         id="DP_RISING",
      12370 +         name="Decision Point Rising",
      12371 +         category="decision_point",
      12372 +         formula_template="""df['up_day'] = df['close'] > df['close'].shift(1)
      12373 + df['breadth'] = df['up_day'].rolling({period}).sum() / {period} * 100
      12374 + df['rising'] = df['breadth'] > df['breadth'].shift(5)
      12375 + df['above_50'] = df['breadth'] > 50
      12376 + df['entry_signal'] = df['rising'] & df['above_50']""",
      12377 +         params={"period": [20, 30]},
      12378 +         direction="long",
      12379 +         lookback=40,
      12380 +         indicators=[],
      12381 +         combinable_with=["volume", "confirmation"],
      12382 +         strategy_type="DPT",
      12383 +     ),
      12384 + ]
      12385 +
      12386 +
      12387 + # =============================================================================
      12388 + # VOLUME WEIGHTED RSI BLOCKS
      12389 + # =============================================================================
      12390 +
      12391 + VOLUME_WEIGHTED_RSI_BLOCKS = [
      12392 +     # VW-RSI Oversold
      12393 +     PatternBlock(
      12394 +         id="VWRSI_OVERSOLD",
      12395 +         name="Volume Weighted RSI Oversold",
      12396 +         category="volume_weighted_rsi",
      12397 +         formula_template="""df['delta'] = df['close'] - df['close'].shift(1)
      12398 + df['up'] = np.where(df['delta'] > 0, df['delta'] * df['volume'], 0)
      12399 + df['down'] = np.where(df['delta'] < 0, -df['delta'] * df['volume'], 0)
      12400 + df['up_avg'] = df['up'].rolling({period}).sum()
      12401 + df['down_avg'] = df['down'].rolling({period}).sum()
      12402 + df['vwrsi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
      12403 + df['oversold'] = df['vwrsi'] < {level}
      12404 + df['entry_signal'] = df['oversold']""",
      12405 +         params={"period": [14], "level": [30, 35]},
      12406 +         direction="long",
      12407 +         lookback=25,
      12408 +         indicators=[],
      12409 +         combinable_with=["momentum", "confirmation"],
      12410 +         strategy_type="VWR",
      12411 +     ),
      12412 +     # VW-RSI Cross Up
      12413 +     PatternBlock(
      12414 +         id="VWRSI_CROSS_UP",
      12415 +         name="Volume Weighted RSI Cross Up",
      12416 +         category="volume_weighted_rsi",
      12417 +         formula_template="""df['delta'] = df['close'] - df['close'].shift(1)
      12418 + df['up'] = np.where(df['delta'] > 0, df['delta'] * df['volume'], 0)
      12419 + df['down'] = np.where(df['delta'] < 0, -df['delta'] * df['volume'], 0)
      12420 + df['up_avg'] = df['up'].rolling({period}).sum()
      12421 + df['down_avg'] = df['down'].rolling({period}).sum()
      12422 + df['vwrsi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
      12423 + df['cross_up'] = (df['vwrsi'] > 50) & (df['vwrsi'].shift(1) <= 50)
      12424 + df['entry_signal'] = df['cross_up']""",
      12425 +         params={"period": [14]},
      12426 +         direction="long",
      12427 +         lookback=25,
      12428 +         indicators=[],
      12429 +         combinable_with=["volume", "threshold"],
      12430 +         strategy_type="VWR",
      12431 +     ),
      12432 +     # VW-RSI Strong
      12433 +     PatternBlock(
      12434 +         id="VWRSI_STRONG",
      12435 +         name="Volume Weighted RSI Strong",
      12436 +         category="volume_weighted_rsi",
      12437 +         formula_template="""df['delta'] = df['close'] - df['close'].shift(1)
      12438 + df['up'] = np.where(df['delta'] > 0, df['delta'] * df['volume'], 0)
      12439 + df['down'] = np.where(df['delta'] < 0, -df['delta'] * df['volume'], 0)
      12440 + df['up_avg'] = df['up'].rolling({period}).sum()
      12441 + df['down_avg'] = df['down'].rolling({period}).sum()
      12442 + df['vwrsi'] = 100 * df['up_avg'] / (df['up_avg'] + df['down_avg'] + 1e-10)
      12443 + df['strong'] = df['vwrsi'] > {level}
      12444 + df['rising'] = df['vwrsi'] > df['vwrsi'].shift(3)
      12445 + df['entry_signal'] = df['strong'] & df['rising']""",
      12446 +         params={"period": [14], "level": [60, 65]},
      12447 +         direction="long",
      12448 +         lookback=25,
      12449 +         indicators=[],
      12450 +         combinable_with=["confirmation", "volume"],
      12451 +         strategy_type="VWR",
      12452 +     ),
      12453 + ]
      12454 +
      12455 +
      12456 + # =============================================================================
      12457   # ALL BLOCKS COMBINED
      12458   # =============================================================================
      12459

● Ora aggiorno ALL_BLOCKS.

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      12622       + INERTIA_BLOCKS
      12623       + KNOW_SURE_THING_BLOCKS
      12624       + SPECIAL_K_BLOCKS
      12625 +     + PERCENTAGE_PRICE_OSC_BLOCKS
      12626 +     + ABSOLUTE_PRICE_OSC_BLOCKS
      12627 +     + DETRENDED_VOLUME_BLOCKS
      12628 +     + RELATIVE_MOMENTUM_BLOCKS
      12629 +     + STOCHASTIC_MOMENTUM_BLOCKS
      12630 +     + PROJECTION_OSC_BLOCKS
      12631 +     + PROJECTION_BANDS_BLOCKS
      12632 +     + PRICE_MOMENTUM_OSC_BLOCKS
      12633 +     + DECISION_POINT_BLOCKS
      12634 +     + VOLUME_WEIGHTED_RSI_BLOCKS
      12635   )
      12636
      12637   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python -c "
      from src.generator.pattern_gen.building_blocks import ALL_BLOCKS, BLOCKS_BY_CATEGORY…)
  ⎿  Total blocks: 628
     Categories: 173
     … +22 lines (ctrl+o to expand)

● Round 17 completato!

  Risultati:
  - Blocchi totali: 628 (da 598, +30)
  - Categorie: 173 (da 163, +10)
  - Validazione: 200/200 OK
  - Strategie stimate: ~127,096

  ---
  Altre possibili migliorie (Round 18)?

  Potrei aggiungere altri ~30 blocchi:

  1. EASE_OF_MOVEMENT_EXT_BLOCKS (3) - EMV extended signals
  2. ACCUMULATION_SWING_BLOCKS (3) - ASI indicator
  3. DEMAND_INDEX_BLOCKS (3) - Demand Index signals
  4. HERRICK_PAYOFF_BLOCKS (3) - Herrick Payoff Index proxy
  5. TRADE_VOLUME_INDEX_BLOCKS (3) - TVI signals
  6. SWING_INDEX_BLOCKS (3) - Swing Index patterns
  7. DYNAMIC_MOMENTUM_BLOCKS (3) - Dynamic momentum index
  8. MARKET_FACILITATION_BLOCKS (3) - MFI Bill Williams style
  9. VOLATILITY_SYSTEM_BLOCKS (3) - Volatility system signals
  10. PRICE_CHANNEL_EXT_BLOCKS (3) - Extended price channels

  Totale: +30 blocchi → 658 blocchi, ~134,000+ strategie

  Vuoi che implementi?

✻ Cogitated for 2m 14s

❯ si

● Search(pattern: "VOLUME_WEIGHTED_RSI_BLOCKS = \[", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 60 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 628 lines
      12454
      12455
      12456   # =============================================================================
      12457 + # EASE OF MOVEMENT EXTENDED BLOCKS
      12458 + # =============================================================================
      12459 +
      12460 + EASE_OF_MOVEMENT_EXT_BLOCKS = [
      12461 +     # EMV Cross Up
      12462 +     PatternBlock(
      12463 +         id="EMV_CROSS_UP_EXT",
      12464 +         name="EMV Cross Up Extended",
      12465 +         category="ease_of_movement_ext",
      12466 +         formula_template="""df['distance'] = ((df['high'] + df['low']) / 2) - ((df['high'].shift(1) + df['low'].shift(1)) / 2)
      12467 + df['box_ratio'] = (df['volume'] / 1e8) / (df['high'] - df['low'] + 1e-10)
      12468 + df['emv'] = df['distance'] / df['box_ratio']
      12469 + df['emv_ma'] = ta.SMA(df['emv'], timeperiod={period})
      12470 + df['cross_up'] = (df['emv'] > df['emv_ma']) & (df['emv'].shift(1) <= df['emv_ma'].shift(1))
      12471 + df['entry_signal'] = df['cross_up']""",
      12472 +         params={"period": [14]},
      12473 +         direction="long",
      12474 +         lookback=25,
      12475 +         indicators=["SMA"],
      12476 +         combinable_with=["volume", "momentum"],
      12477 +         strategy_type="EMX",
      12478 +     ),
      12479 +     # EMV Positive Strong
      12480 +     PatternBlock(
      12481 +         id="EMV_POSITIVE_STRONG",
      12482 +         name="EMV Positive Strong",
      12483 +         category="ease_of_movement_ext",
      12484 +         formula_template="""df['distance'] = ((df['high'] + df['low']) / 2) - ((df['high'].shift(1) + df['low'].shift(1)) / 2)
      12485 + df['box_ratio'] = (df['volume'] / 1e8) / (df['high'] - df['low'] + 1e-10)
      12486 + df['emv'] = df['distance'] / df['box_ratio']
      12487 + df['emv_ma'] = ta.SMA(df['emv'], timeperiod={period})
      12488 + df['positive'] = df['emv_ma'] > 0
      12489 + df['rising'] = df['emv_ma'] > df['emv_ma'].shift(3)
      12490 + df['entry_signal'] = df['positive'] & df['rising']""",
      12491 +         params={"period": [14]},
      12492 +         direction="long",
      12493 +         lookback=25,
      12494 +         indicators=["SMA"],
      12495 +         combinable_with=["confirmation", "threshold"],
      12496 +         strategy_type="EMX",
      12497 +     ),
      12498 +     # EMV Zero Cross
      12499 +     PatternBlock(
      12500 +         id="EMV_ZERO_CROSS_EXT",
      12501 +         name="EMV Zero Cross Extended",
      12502 +         category="ease_of_movement_ext",
      12503 +         formula_template="""df['distance'] = ((df['high'] + df['low']) / 2) - ((df['high'].shift(1) + df['low'].shift(1)) / 2)
      12504 + df['box_ratio'] = (df['volume'] / 1e8) / (df['high'] - df['low'] + 1e-10)
      12505 + df['emv'] = df['distance'] / df['box_ratio']
      12506 + df['emv_ma'] = ta.SMA(df['emv'], timeperiod={period})
      12507 + df['cross_zero'] = (df['emv_ma'] > 0) & (df['emv_ma'].shift(1) <= 0)
      12508 + df['entry_signal'] = df['cross_zero']""",
      12509 +         params={"period": [14]},
      12510 +         direction="long",
      12511 +         lookback=25,
      12512 +         indicators=["SMA"],
      12513 +         combinable_with=["volume", "confirmation"],
      12514 +         strategy_type="EMX",
      12515 +     ),
      12516 + ]
      12517 +
      12518 +
      12519 + # =============================================================================
      12520 + # ACCUMULATION SWING INDEX BLOCKS
      12521 + # =============================================================================
      12522 +
      12523 + ACCUMULATION_SWING_BLOCKS = [
      12524 +     # ASI Rising
      12525 +     PatternBlock(
      12526 +         id="ASI_RISING",
      12527 +         name="Accumulation Swing Rising",
      12528 +         category="accumulation_swing",
      12529 +         formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
      12530 + df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] -
            +df['close'].shift(1))))
      12531 + df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open']) + 0.25 * (df['close'].shift(1) -
            +df['open'].shift(1))) / df['tr'] * df['k'] / df['tr']
      12532 + df['asi'] = df['si'].cumsum()
      12533 + df['asi_ma'] = ta.SMA(df['asi'], timeperiod={period})
      12534 + df['rising'] = df['asi'] > df['asi_ma']
      12535 + df['asi_up'] = df['asi'] > df['asi'].shift(3)
      12536 + df['entry_signal'] = df['rising'] & df['asi_up']""",
      12537 +         params={"period": [14]},
      12538 +         direction="long",
      12539 +         lookback=30,
      12540 +         indicators=["SMA"],
      12541 +         combinable_with=["volume", "momentum"],
      12542 +         strategy_type="ASI",
      12543 +     ),
      12544 +     # ASI Breakout
      12545 +     PatternBlock(
      12546 +         id="ASI_BREAKOUT",
      12547 +         name="Accumulation Swing Breakout",
      12548 +         category="accumulation_swing",
      12549 +         formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
      12550 + df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] -
            +df['close'].shift(1))))
      12551 + df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open']) + 0.25 * (df['close'].shift(1) -
            +df['open'].shift(1))) / df['tr'] * df['k'] / df['tr']
      12552 + df['asi'] = df['si'].cumsum()
      12553 + df['asi_high'] = df['asi'].rolling({period}).max()
      12554 + df['breakout'] = df['asi'] > df['asi_high'].shift(1)
      12555 + df['entry_signal'] = df['breakout']""",
      12556 +         params={"period": [20]},
      12557 +         direction="long",
      12558 +         lookback=30,
      12559 +         indicators=[],
      12560 +         combinable_with=["confirmation", "threshold"],
      12561 +         strategy_type="ASI",
      12562 +     ),
      12563 +     # ASI Divergence
      12564 +     PatternBlock(
      12565 +         id="ASI_DIVERGENCE",
      12566 +         name="Accumulation Swing Divergence",
      12567 +         category="accumulation_swing",
      12568 +         formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
      12569 + df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] -
            +df['close'].shift(1))))
      12570 + df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open']) + 0.25 * (df['close'].shift(1) -
            +df['open'].shift(1))) / df['tr'] * df['k'] / df['tr']
      12571 + df['asi'] = df['si'].cumsum()
      12572 + df['price_lower'] = df['close'] < df['close'].shift({lookback})
      12573 + df['asi_higher'] = df['asi'] > df['asi'].shift({lookback})
      12574 + df['divergence'] = df['price_lower'] & df['asi_higher']
      12575 + df['entry_signal'] = df['divergence']""",
      12576 +         params={"lookback": [5, 10]},
      12577 +         direction="long",
      12578 +         lookback=30,
      12579 +         indicators=[],
      12580 +         combinable_with=["volume", "confirmation"],
      12581 +         strategy_type="ASI",
      12582 +     ),
      12583 + ]
      12584 +
      12585 +
      12586 + # =============================================================================
      12587 + # DEMAND INDEX BLOCKS
      12588 + # =============================================================================
      12589 +
      12590 + DEMAND_INDEX_BLOCKS = [
      12591 +     # Demand Index Positive
      12592 +     PatternBlock(
      12593 +         id="DI_POSITIVE",
      12594 +         name="Demand Index Positive",
      12595 +         category="demand_index",
      12596 +         formula_template="""df['bp'] = df['close'] - df['low']
      12597 + df['sp'] = df['high'] - df['close']
      12598 + df['bp_vol'] = df['bp'] * df['volume']
      12599 + df['sp_vol'] = df['sp'] * df['volume']
      12600 + df['di'] = df['bp_vol'].rolling({period}).sum() / (df['sp_vol'].rolling({period}).sum() + 1e-10)
      12601 + df['positive'] = df['di'] > 1.0
      12602 + df['rising'] = df['di'] > df['di'].shift(3)
      12603 + df['entry_signal'] = df['positive'] & df['rising']""",
      12604 +         params={"period": [14, 20]},
      12605 +         direction="long",
      12606 +         lookback=30,
      12607 +         indicators=[],
      12608 +         combinable_with=["volume", "momentum"],
      12609 +         strategy_type="DMI",
      12610 +     ),
      12611 +     # Demand Index Cross
      12612 +     PatternBlock(
      12613 +         id="DI_CROSS",
      12614 +         name="Demand Index Cross",
      12615 +         category="demand_index",
      12616 +         formula_template="""df['bp'] = df['close'] - df['low']
      12617 + df['sp'] = df['high'] - df['close']
      12618 + df['bp_vol'] = df['bp'] * df['volume']
      12619 + df['sp_vol'] = df['sp'] * df['volume']
      12620 + df['di'] = df['bp_vol'].rolling({period}).sum() / (df['sp_vol'].rolling({period}).sum() + 1e-10)
      12621 + df['cross_up'] = (df['di'] > 1.0) & (df['di'].shift(1) <= 1.0)
      12622 + df['entry_signal'] = df['cross_up']""",
      12623 +         params={"period": [14]},
      12624 +         direction="long",
      12625 +         lookback=25,
      12626 +         indicators=[],
      12627 +         combinable_with=["confirmation", "threshold"],
      12628 +         strategy_type="DMI",
      12629 +     ),
      12630 +     # Demand Index Strong
      12631 +     PatternBlock(
      12632 +         id="DI_STRONG",
      12633 +         name="Demand Index Strong",
      12634 +         category="demand_index",
      12635 +         formula_template="""df['bp'] = df['close'] - df['low']
      12636 + df['sp'] = df['high'] - df['close']
      12637 + df['bp_vol'] = df['bp'] * df['volume']
      12638 + df['sp_vol'] = df['sp'] * df['volume']
      12639 + df['di'] = df['bp_vol'].rolling({period}).sum() / (df['sp_vol'].rolling({period}).sum() + 1e-10)
      12640 + df['strong'] = df['di'] > {threshold}
      12641 + df['entry_signal'] = df['strong']""",
      12642 +         params={"period": [14], "threshold": [1.5, 2.0]},
      12643 +         direction="long",
      12644 +         lookback=25,
      12645 +         indicators=[],
      12646 +         combinable_with=["volume", "confirmation"],
      12647 +         strategy_type="DMI",
      12648 +     ),
      12649 + ]
      12650 +
      12651 +
      12652 + # =============================================================================
      12653 + # HERRICK PAYOFF INDEX BLOCKS (proxy)
      12654 + # =============================================================================
      12655 +
      12656 + HERRICK_PAYOFF_BLOCKS = [
      12657 +     # HPI Rising
      12658 +     PatternBlock(
      12659 +         id="HPI_RISING",
      12660 +         name="Herrick Payoff Rising",
      12661 +         category="herrick_payoff",
      12662 +         formula_template="""df['mean_price'] = (df['high'] + df['low']) / 2
      12663 + df['mean_change'] = df['mean_price'] - df['mean_price'].shift(1)
      12664 + df['vol_factor'] = df['volume'] / df['volume'].rolling({period}).mean()
      12665 + df['hpi'] = df['mean_change'] * df['vol_factor']
      12666 + df['hpi_cum'] = df['hpi'].rolling({period}).sum()
      12667 + df['rising'] = df['hpi_cum'] > df['hpi_cum'].shift(3)
      12668 + df['positive'] = df['hpi_cum'] > 0
      12669 + df['entry_signal'] = df['rising'] & df['positive']""",
      12670 +         params={"period": [14, 20]},
      12671 +         direction="long",
      12672 +         lookback=30,
      12673 +         indicators=[],
      12674 +         combinable_with=["volume", "momentum"],
      12675 +         strategy_type="HPI",
      12676 +     ),
      12677 +     # HPI Cross Zero
      12678 +     PatternBlock(
      12679 +         id="HPI_CROSS_ZERO",
      12680 +         name="Herrick Payoff Cross Zero",
      12681 +         category="herrick_payoff",
      12682 +         formula_template="""df['mean_price'] = (df['high'] + df['low']) / 2
      12683 + df['mean_change'] = df['mean_price'] - df['mean_price'].shift(1)
      12684 + df['vol_factor'] = df['volume'] / df['volume'].rolling({period}).mean()
      12685 + df['hpi'] = df['mean_change'] * df['vol_factor']
      12686 + df['hpi_cum'] = df['hpi'].rolling({period}).sum()
      12687 + df['cross_zero'] = (df['hpi_cum'] > 0) & (df['hpi_cum'].shift(1) <= 0)
      12688 + df['entry_signal'] = df['cross_zero']""",
      12689 +         params={"period": [14]},
      12690 +         direction="long",
      12691 +         lookback=25,
      12692 +         indicators=[],
      12693 +         combinable_with=["confirmation", "threshold"],
      12694 +         strategy_type="HPI",
      12695 +     ),
      12696 +     # HPI Divergence
      12697 +     PatternBlock(
      12698 +         id="HPI_DIVERGENCE",
      12699 +         name="Herrick Payoff Divergence",
      12700 +         category="herrick_payoff",
      12701 +         formula_template="""df['mean_price'] = (df['high'] + df['low']) / 2
      12702 + df['mean_change'] = df['mean_price'] - df['mean_price'].shift(1)
      12703 + df['vol_factor'] = df['volume'] / df['volume'].rolling({period}).mean()
      12704 + df['hpi'] = df['mean_change'] * df['vol_factor']
      12705 + df['hpi_cum'] = df['hpi'].rolling({period}).sum()
      12706 + df['price_lower'] = df['close'] < df['close'].shift(5)
      12707 + df['hpi_higher'] = df['hpi_cum'] > df['hpi_cum'].shift(5)
      12708 + df['divergence'] = df['price_lower'] & df['hpi_higher']
      12709 + df['entry_signal'] = df['divergence']""",
      12710 +         params={"period": [14]},
      12711 +         direction="long",
      12712 +         lookback=30,
      12713 +         indicators=[],
      12714 +         combinable_with=["volume", "confirmation"],
      12715 +         strategy_type="HPI",
      12716 +     ),
      12717 + ]
      12718 +
      12719 +
      12720 + # =============================================================================
      12721 + # TRADE VOLUME INDEX BLOCKS
      12722 + # =============================================================================
      12723 +
      12724 + TRADE_VOLUME_INDEX_BLOCKS = [
      12725 +     # TVI Rising
      12726 +     PatternBlock(
      12727 +         id="TVI_RISING",
      12728 +         name="Trade Volume Index Rising",
      12729 +         category="trade_volume_index",
      12730 +         formula_template="""df['direction'] = np.sign(df['close'] - df['close'].shift(1))
      12731 + df['tvi'] = (df['direction'] * df['volume']).cumsum()
      12732 + df['tvi_ma'] = ta.SMA(df['tvi'], timeperiod={period})
      12733 + df['rising'] = df['tvi'] > df['tvi_ma']
      12734 + df['tvi_up'] = df['tvi'] > df['tvi'].shift(3)
      12735 + df['entry_signal'] = df['rising'] & df['tvi_up']""",
      12736 +         params={"period": [14, 20]},
      12737 +         direction="long",
      12738 +         lookback=30,
      12739 +         indicators=["SMA"],
      12740 +         combinable_with=["momentum", "threshold"],
      12741 +         strategy_type="TVI",
      12742 +     ),
      12743 +     # TVI Cross Up
      12744 +     PatternBlock(
      12745 +         id="TVI_CROSS_UP",
      12746 +         name="Trade Volume Index Cross Up",
      12747 +         category="trade_volume_index",
      12748 +         formula_template="""df['direction'] = np.sign(df['close'] - df['close'].shift(1))
      12749 + df['tvi'] = (df['direction'] * df['volume']).cumsum()
      12750 + df['tvi_ma'] = ta.SMA(df['tvi'], timeperiod={period})
      12751 + df['cross_up'] = (df['tvi'] > df['tvi_ma']) & (df['tvi'].shift(1) <= df['tvi_ma'].shift(1))
      12752 + df['entry_signal'] = df['cross_up']""",
      12753 +         params={"period": [14]},
      12754 +         direction="long",
      12755 +         lookback=25,
      12756 +         indicators=["SMA"],
      12757 +         combinable_with=["volume", "confirmation"],
      12758 +         strategy_type="TVI",
      12759 +     ),
      12760 +     # TVI Breakout
      12761 +     PatternBlock(
      12762 +         id="TVI_BREAKOUT",
      12763 +         name="Trade Volume Index Breakout",
      12764 +         category="trade_volume_index",
      12765 +         formula_template="""df['direction'] = np.sign(df['close'] - df['close'].shift(1))
      12766 + df['tvi'] = (df['direction'] * df['volume']).cumsum()
      12767 + df['tvi_high'] = df['tvi'].rolling({period}).max()
      12768 + df['breakout'] = df['tvi'] > df['tvi_high'].shift(1)
      12769 + df['entry_signal'] = df['breakout']""",
      12770 +         params={"period": [20]},
      12771 +         direction="long",
      12772 +         lookback=30,
      12773 +         indicators=[],
      12774 +         combinable_with=["confirmation", "momentum"],
      12775 +         strategy_type="TVI",
      12776 +     ),
      12777 + ]
      12778 +
      12779 +
      12780 + # =============================================================================
      12781 + # SWING INDEX BLOCKS
      12782 + # =============================================================================
      12783 +
      12784 + SWING_INDEX_BLOCKS = [
      12785 +     # Swing Index Positive
      12786 +     PatternBlock(
      12787 +         id="SI_POSITIVE",
      12788 +         name="Swing Index Positive",
      12789 +         category="swing_index",
      12790 +         formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
      12791 + df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] -
            +df['close'].shift(1))))
      12792 + df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open'])) / (df['tr'] + 1e-10)
      12793 + df['si_ma'] = ta.SMA(df['si'], timeperiod={period})
      12794 + df['positive'] = df['si_ma'] > 0
      12795 + df['rising'] = df['si_ma'] > df['si_ma'].shift(3)
      12796 + df['entry_signal'] = df['positive'] & df['rising']""",
      12797 +         params={"period": [14]},
      12798 +         direction="long",
      12799 +         lookback=25,
      12800 +         indicators=["SMA"],
      12801 +         combinable_with=["volume", "momentum"],
      12802 +         strategy_type="SWI",
      12803 +     ),
      12804 +     # Swing Index Cross
      12805 +     PatternBlock(
      12806 +         id="SI_CROSS",
      12807 +         name="Swing Index Cross",
      12808 +         category="swing_index",
      12809 +         formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
      12810 + df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] -
            +df['close'].shift(1))))
      12811 + df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open'])) / (df['tr'] + 1e-10)
      12812 + df['si_ma'] = ta.SMA(df['si'], timeperiod={period})
      12813 + df['cross_up'] = (df['si_ma'] > 0) & (df['si_ma'].shift(1) <= 0)
      12814 + df['entry_signal'] = df['cross_up']""",
      12815 +         params={"period": [14]},
      12816 +         direction="long",
      12817 +         lookback=25,
      12818 +         indicators=["SMA"],
      12819 +         combinable_with=["confirmation", "threshold"],
      12820 +         strategy_type="SWI",
      12821 +     ),
      12822 +     # Swing Index Strong
      12823 +     PatternBlock(
      12824 +         id="SI_STRONG",
      12825 +         name="Swing Index Strong",
      12826 +         category="swing_index",
      12827 +         formula_template="""df['k'] = np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1)))
      12828 + df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] -
            +df['close'].shift(1))))
      12829 + df['si'] = 50 * (df['close'] - df['close'].shift(1) + 0.5 * (df['close'] - df['open'])) / (df['tr'] + 1e-10)
      12830 + df['si_sum'] = df['si'].rolling({period}).sum()
      12831 + df['strong'] = df['si_sum'] > df['si_sum'].rolling({period}).std() * {mult}
      12832 + df['entry_signal'] = df['strong']""",
      12833 +         params={"period": [14], "mult": [1.5, 2.0]},
      12834 +         direction="long",
      12835 +         lookback=30,
      12836 +         indicators=[],
      12837 +         combinable_with=["volume", "confirmation"],
      12838 +         strategy_type="SWI",
      12839 +     ),
      12840 + ]
      12841 +
      12842 +
      12843 + # =============================================================================
      12844 + # DYNAMIC MOMENTUM INDEX BLOCKS
      12845 + # =============================================================================
      12846 +
      12847 + DYNAMIC_MOMENTUM_BLOCKS = [
      12848 +     # DMI Oversold
      12849 +     PatternBlock(
      12850 +         id="DYMI_OVERSOLD",
      12851 +         name="Dynamic Momentum Oversold",
      12852 +         category="dynamic_momentum",
      12853 +         formula_template="""df['vol'] = df['close'].rolling(5).std()
      12854 + df['vol_avg'] = df['vol'].rolling(10).mean()
      12855 + df['dyn_period'] = np.clip(14 * df['vol_avg'] / (df['vol'] + 1e-10), 5, 30).astype(int)
      12856 + df['dymi'] = ta.RSI(df['close'], timeperiod=14)
      12857 + df['oversold'] = df['dymi'] < {level}
      12858 + df['entry_signal'] = df['oversold']""",
      12859 +         params={"level": [30, 35]},
      12860 +         direction="long",
      12861 +         lookback=35,
      12862 +         indicators=["RSI"],
      12863 +         combinable_with=["volume", "confirmation"],
      12864 +         strategy_type="DYM",
      12865 +     ),
      12866 +     # DMI Cross Up
      12867 +     PatternBlock(
      12868 +         id="DYMI_CROSS_UP",
      12869 +         name="Dynamic Momentum Cross Up",
      12870 +         category="dynamic_momentum",
      12871 +         formula_template="""df['dymi'] = ta.RSI(df['close'], timeperiod=14)
      12872 + df['dymi_ma'] = ta.SMA(df['dymi'], timeperiod=9)
      12873 + df['cross_up'] = (df['dymi'] > df['dymi_ma']) & (df['dymi'].shift(1) <= df['dymi_ma'].shift(1))
      12874 + df['entry_signal'] = df['cross_up']""",
      12875 +         params={},
      12876 +         direction="long",
      12877 +         lookback=30,
      12878 +         indicators=["RSI", "SMA"],
      12879 +         combinable_with=["momentum", "threshold"],
      12880 +         strategy_type="DYM",
      12881 +     ),
      12882 +     # DMI Strong
      12883 +     PatternBlock(
      12884 +         id="DYMI_STRONG",
      12885 +         name="Dynamic Momentum Strong",
      12886 +         category="dynamic_momentum",
      12887 +         formula_template="""df['dymi'] = ta.RSI(df['close'], timeperiod=14)
      12888 + df['strong'] = df['dymi'] > {level}
      12889 + df['rising'] = df['dymi'] > df['dymi'].shift(3)
      12890 + df['entry_signal'] = df['strong'] & df['rising']""",
      12891 +         params={"level": [60, 65]},
      12892 +         direction="long",
      12893 +         lookback=25,
      12894 +         indicators=["RSI"],
      12895 +         combinable_with=["volume", "confirmation"],
      12896 +         strategy_type="DYM",
      12897 +     ),
      12898 + ]
      12899 +
      12900 +
      12901 + # =============================================================================
      12902 + # MARKET FACILITATION INDEX BLOCKS (Bill Williams)
      12903 + # =============================================================================
      12904 +
      12905 + MARKET_FACILITATION_BLOCKS = [
      12906 +     # MFI Green (price up, volume up)
      12907 +     PatternBlock(
      12908 +         id="MFI_GREEN",
      12909 +         name="Market Facilitation Green",
      12910 +         category="market_facilitation",
      12911 +         formula_template="""df['mfi'] = (df['high'] - df['low']) / (df['volume'] + 1e-10) * 1e8
      12912 + df['mfi_up'] = df['mfi'] > df['mfi'].shift(1)
      12913 + df['vol_up'] = df['volume'] > df['volume'].shift(1)
      12914 + df['green'] = df['mfi_up'] & df['vol_up']
      12915 + df['entry_signal'] = df['green']""",
      12916 +         params={},
      12917 +         direction="long",
      12918 +         lookback=10,
      12919 +         indicators=[],
      12920 +         combinable_with=["momentum", "threshold"],
      12921 +         strategy_type="MFB",
      12922 +     ),
      12923 +     # MFI Squat (MFI down, volume up)
      12924 +     PatternBlock(
      12925 +         id="MFI_SQUAT",
      12926 +         name="Market Facilitation Squat",
      12927 +         category="market_facilitation",
      12928 +         formula_template="""df['mfi'] = (df['high'] - df['low']) / (df['volume'] + 1e-10) * 1e8
      12929 + df['mfi_down'] = df['mfi'] < df['mfi'].shift(1)
      12930 + df['vol_up'] = df['volume'] > df['volume'].shift(1)
      12931 + df['squat'] = df['mfi_down'] & df['vol_up']
      12932 + df['squat_count'] = df['squat'].rolling(3).sum() >= 2
      12933 + df['price_up'] = df['close'] > df['close'].shift(3)
      12934 + df['entry_signal'] = df['squat_count'] & df['price_up']""",
      12935 +         params={},
      12936 +         direction="long",
      12937 +         lookback=15,
      12938 +         indicators=[],
      12939 +         combinable_with=["volume", "confirmation"],
      12940 +         strategy_type="MFB",
      12941 +     ),
      12942 +     # MFI Fade Recovery
      12943 +     PatternBlock(
      12944 +         id="MFI_FADE_RECOVERY",
      12945 +         name="Market Facilitation Fade Recovery",
      12946 +         category="market_facilitation",
      12947 +         formula_template="""df['mfi'] = (df['high'] - df['low']) / (df['volume'] + 1e-10) * 1e8
      12948 + df['mfi_down'] = df['mfi'] < df['mfi'].shift(1)
      12949 + df['vol_down'] = df['volume'] < df['volume'].shift(1)
      12950 + df['fade'] = df['mfi_down'] & df['vol_down']
      12951 + df['was_fade'] = df['fade'].shift(1)
      12952 + df['mfi_rising'] = df['mfi'] > df['mfi'].shift(1)
      12953 + df['recovery'] = df['was_fade'] & df['mfi_rising']
      12954 + df['entry_signal'] = df['recovery']""",
      12955 +         params={},
      12956 +         direction="bidi",
      12957 +         lookback=15,
      12958 +         indicators=[],
      12959 +         combinable_with=["momentum", "confirmation"],
      12960 +         strategy_type="MFB",
      12961 +     ),
      12962 + ]
      12963 +
      12964 +
      12965 + # =============================================================================
      12966 + # VOLATILITY SYSTEM BLOCKS
      12967 + # =============================================================================
      12968 +
      12969 + VOLATILITY_SYSTEM_BLOCKS = [
      12970 +     # Volatility Breakout Up
      12971 +     PatternBlock(
      12972 +         id="VOL_SYS_BREAKOUT_UP",
      12973 +         name="Volatility System Breakout Up",
      12974 +         category="volatility_system",
      12975 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      12976 + df['upper'] = df['close'].shift(1) + df['atr'].shift(1) * {mult}
      12977 + df['breakout'] = df['close'] > df['upper']
      12978 + df['entry_signal'] = df['breakout']""",
      12979 +         params={"period": [14], "mult": [1.5, 2.0]},
      12980 +         direction="long",
      12981 +         lookback=25,
      12982 +         indicators=["ATR"],
      12983 +         combinable_with=["volume", "momentum"],
      12984 +         strategy_type="VSY",
      12985 +     ),
      12986 +     # Volatility Contraction Breakout
      12987 +     PatternBlock(
      12988 +         id="VOL_SYS_CONTRACT_BREAK",
      12989 +         name="Volatility Contraction Breakout",
      12990 +         category="volatility_system",
      12991 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      12992 + df['atr_ma'] = df['atr'].rolling({period}).mean()
      12993 + df['contracted'] = df['atr'] < df['atr_ma'] * {contract}
      12994 + df['contracted_days'] = df['contracted'].rolling(5).sum() >= 3
      12995 + df['breakout'] = df['close'] > df['high'].shift(1)
      12996 + df['entry_signal'] = df['contracted_days'] & df['breakout']""",
      12997 +         params={"period": [14], "contract": [0.7, 0.8]},
      12998 +         direction="long",
      12999 +         lookback=30,
      13000 +         indicators=["ATR"],
      13001 +         combinable_with=["confirmation", "threshold"],
      13002 +         strategy_type="VSY",
      13003 +     ),
      13004 +     # Volatility Expansion Entry
      13005 +     PatternBlock(
      13006 +         id="VOL_SYS_EXPANSION",
      13007 +         name="Volatility System Expansion",
      13008 +         category="volatility_system",
      13009 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod={period})
      13010 + df['atr_ma'] = df['atr'].rolling({period}).mean()
      13011 + df['expansion'] = df['atr'] > df['atr_ma'] * {expand}
      13012 + df['price_up'] = df['close'] > df['close'].shift(1)
      13013 + df['entry_signal'] = df['expansion'] & df['price_up']""",
      13014 +         params={"period": [14], "expand": [1.2, 1.5]},
      13015 +         direction="long",
      13016 +         lookback=25,
      13017 +         indicators=["ATR"],
      13018 +         combinable_with=["volume", "confirmation"],
      13019 +         strategy_type="VSY",
      13020 +     ),
      13021 + ]
      13022 +
      13023 +
      13024 + # =============================================================================
      13025 + # PRICE CHANNEL EXTENDED BLOCKS
      13026 + # =============================================================================
      13027 +
      13028 + PRICE_CHANNEL_EXT_BLOCKS = [
      13029 +     # Price Channel Breakout Up
      13030 +     PatternBlock(
      13031 +         id="PCH_BREAKOUT_UP",
      13032 +         name="Price Channel Breakout Up",
      13033 +         category="price_channel_ext",
      13034 +         formula_template="""df['upper'] = df['high'].rolling({period}).max().shift(1)
      13035 + df['lower'] = df['low'].rolling({period}).min().shift(1)
      13036 + df['breakout'] = df['close'] > df['upper']
      13037 + df['entry_signal'] = df['breakout']""",
      13038 +         params={"period": [20, 30]},
      13039 +         direction="long",
      13040 +         lookback=35,
      13041 +         indicators=[],
      13042 +         combinable_with=["volume", "momentum"],
      13043 +         strategy_type="PCE",
      13044 +     ),
      13045 +     # Price Channel Mid Cross
      13046 +     PatternBlock(
      13047 +         id="PCH_MID_CROSS",
      13048 +         name="Price Channel Mid Cross",
      13049 +         category="price_channel_ext",
      13050 +         formula_template="""df['upper'] = df['high'].rolling({period}).max()
      13051 + df['lower'] = df['low'].rolling({period}).min()
      13052 + df['mid'] = (df['upper'] + df['lower']) / 2
      13053 + df['cross_up'] = (df['close'] > df['mid']) & (df['close'].shift(1) <= df['mid'].shift(1))
      13054 + df['entry_signal'] = df['cross_up']""",
      13055 +         params={"period": [20]},
      13056 +         direction="long",
      13057 +         lookback=30,
      13058 +         indicators=[],
      13059 +         combinable_with=["confirmation", "threshold"],
      13060 +         strategy_type="PCE",
      13061 +     ),
      13062 +     # Price Channel Width
      13063 +     PatternBlock(
      13064 +         id="PCH_WIDTH_EXPAND",
      13065 +         name="Price Channel Width Expanding",
      13066 +         category="price_channel_ext",
      13067 +         formula_template="""df['upper'] = df['high'].rolling({period}).max()
      13068 + df['lower'] = df['low'].rolling({period}).min()
      13069 + df['width'] = (df['upper'] - df['lower']) / df['close']
      13070 + df['width_ma'] = df['width'].rolling({period}).mean()
      13071 + df['expanding'] = df['width'] > df['width_ma'] * {mult}
      13072 + df['uptrend'] = df['close'] > (df['upper'] + df['lower']) / 2
      13073 + df['entry_signal'] = df['expanding'] & df['uptrend']""",
      13074 +         params={"period": [20], "mult": [1.2, 1.3]},
      13075 +         direction="long",
      13076 +         lookback=35,
      13077 +         indicators=[],
      13078 +         combinable_with=["volume", "confirmation"],
      13079 +         strategy_type="PCE",
      13080 +     ),
      13081 + ]
      13082 +
      13083 +
      13084 + # =============================================================================
      13085   # ALL BLOCKS COMBINED
      13086   # =============================================================================
      13087

● Ora aggiorno ALL_BLOCKS.

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      13260       + PRICE_MOMENTUM_OSC_BLOCKS
      13261       + DECISION_POINT_BLOCKS
      13262       + VOLUME_WEIGHTED_RSI_BLOCKS
      13263 +     + EASE_OF_MOVEMENT_EXT_BLOCKS
      13264 +     + ACCUMULATION_SWING_BLOCKS
      13265 +     + DEMAND_INDEX_BLOCKS
      13266 +     + HERRICK_PAYOFF_BLOCKS
      13267 +     + TRADE_VOLUME_INDEX_BLOCKS
      13268 +     + SWING_INDEX_BLOCKS
      13269 +     + DYNAMIC_MOMENTUM_BLOCKS
      13270 +     + MARKET_FACILITATION_BLOCKS
      13271 +     + VOLATILITY_SYSTEM_BLOCKS
      13272 +     + PRICE_CHANNEL_EXT_BLOCKS
      13273   )
      13274
      13275   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python -c "
      from src.generator.pattern_gen.building_blocks import ALL_BLOCKS, BLOCKS_BY_CATEGORY…)
  ⎿  Total blocks: 658
     Categories: 183
     … +22 lines (ctrl+o to expand)

● Round 18 completato!

  Risultati:
  - Blocchi totali: 658 (da 628, +30)
  - Categorie: 183 (da 173, +10)
  - Validazione: 200/200 OK
  - Strategie stimate: ~131,432

  ---
  Altre possibili migliorie (Round 19)?

  Potrei aggiungere altri ~30 blocchi:

  1. BALANCE_OF_POWER_EXT_BLOCKS (3) - BOP extended signals
  2. CHAIKIN_VOLATILITY_BLOCKS (3) - Chaikin Volatility
  3. HISTORICAL_VOLATILITY_BLOCKS (3) - HV indicator signals
  4. STANDARD_ERROR_BLOCKS (3) - Standard error bands
  5. REGRESSION_SLOPE_BLOCKS (3) - Regression slope signals
  6. PRICE_OSCILLATOR_EXT_BLOCKS (3) - Extended price oscillator
  7. VOLUME_OSCILLATOR_BLOCKS (3) - Volume oscillator
  8. MOMENTUM_PERCENTILE_BLOCKS (3) - Momentum percentile
  9. TREND_SCORE_BLOCKS (3) - Composite trend scoring
  10. ADAPTIVE_RSI_BLOCKS (3) - Adaptive period RSI

  Totale: +30 blocchi → 688 blocchi, ~139,000+ strategie

  Vuoi che implementi?

✻ Worked for 2m 14s

❯ si

● Search(pattern: "PRICE_CHANNEL_EXT_BLOCKS = \[", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 60 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 611 lines
      13082
      13083
      13084   # =============================================================================
      13085 + # BALANCE OF POWER EXTENDED BLOCKS
      13086 + # =============================================================================
      13087 +
      13088 + BALANCE_OF_POWER_EXT_BLOCKS = [
      13089 +     # BOP Cross Up
      13090 +     PatternBlock(
      13091 +         id="BOP_CROSS_UP_EXT",
      13092 +         name="BOP Cross Up Extended",
      13093 +         category="balance_of_power_ext",
      13094 +         formula_template="""df['bop'] = ta.BOP(df['open'], df['high'], df['low'], df['close'])
      13095 + df['bop_ma'] = ta.SMA(df['bop'], timeperiod={period})
      13096 + df['cross_up'] = (df['bop'] > df['bop_ma']) & (df['bop'].shift(1) <= df['bop_ma'].shift(1))
      13097 + df['entry_signal'] = df['cross_up']""",
      13098 +         params={"period": [14]},
      13099 +         direction="long",
      13100 +         lookback=25,
      13101 +         indicators=["BOP", "SMA"],
      13102 +         combinable_with=["volume", "momentum"],
      13103 +         strategy_type="BPX",
      13104 +     ),
      13105 +     # BOP Strong Positive
      13106 +     PatternBlock(
      13107 +         id="BOP_STRONG_POS",
      13108 +         name="BOP Strong Positive",
      13109 +         category="balance_of_power_ext",
      13110 +         formula_template="""df['bop'] = ta.BOP(df['open'], df['high'], df['low'], df['close'])
      13111 + df['bop_ma'] = ta.SMA(df['bop'], timeperiod={period})
      13112 + df['strong'] = df['bop_ma'] > {threshold}
      13113 + df['rising'] = df['bop_ma'] > df['bop_ma'].shift(3)
      13114 + df['entry_signal'] = df['strong'] & df['rising']""",
      13115 +         params={"period": [14], "threshold": [0.3, 0.4]},
      13116 +         direction="long",
      13117 +         lookback=25,
      13118 +         indicators=["BOP", "SMA"],
      13119 +         combinable_with=["confirmation", "threshold"],
      13120 +         strategy_type="BPX",
      13121 +     ),
      13122 +     # BOP Zero Cross
      13123 +     PatternBlock(
      13124 +         id="BOP_ZERO_CROSS_EXT",
      13125 +         name="BOP Zero Cross Extended",
      13126 +         category="balance_of_power_ext",
      13127 +         formula_template="""df['bop'] = ta.BOP(df['open'], df['high'], df['low'], df['close'])
      13128 + df['bop_ma'] = ta.SMA(df['bop'], timeperiod={period})
      13129 + df['cross_zero'] = (df['bop_ma'] > 0) & (df['bop_ma'].shift(1) <= 0)
      13130 + df['entry_signal'] = df['cross_zero']""",
      13131 +         params={"period": [14]},
      13132 +         direction="long",
      13133 +         lookback=25,
      13134 +         indicators=["BOP", "SMA"],
      13135 +         combinable_with=["volume", "confirmation"],
      13136 +         strategy_type="BPX",
      13137 +     ),
      13138 + ]
      13139 +
      13140 +
      13141 + # =============================================================================
      13142 + # CHAIKIN VOLATILITY BLOCKS
      13143 + # =============================================================================
      13144 +
      13145 + CHAIKIN_VOLATILITY_BLOCKS = [
      13146 +     # Chaikin Vol Rising
      13147 +     PatternBlock(
      13148 +         id="CHAIKIN_VOL_RISING",
      13149 +         name="Chaikin Volatility Rising",
      13150 +         category="chaikin_volatility",
      13151 +         formula_template="""df['hl'] = df['high'] - df['low']
      13152 + df['hl_ema'] = ta.EMA(df['hl'], timeperiod={period})
      13153 + df['chv'] = (df['hl_ema'] - df['hl_ema'].shift({period})) / (df['hl_ema'].shift({period}) + 1e-10) * 100
      13154 + df['rising'] = df['chv'] > df['chv'].shift(1)
      13155 + df['positive'] = df['chv'] > 0
      13156 + df['entry_signal'] = df['rising'] & df['positive']""",
      13157 +         params={"period": [10]},
      13158 +         direction="bidi",
      13159 +         lookback=25,
      13160 +         indicators=["EMA"],
      13161 +         combinable_with=["momentum", "threshold"],
      13162 +         strategy_type="CHV",
      13163 +     ),
      13164 +     # Chaikin Vol Extreme Low
      13165 +     PatternBlock(
      13166 +         id="CHAIKIN_VOL_LOW",
      13167 +         name="Chaikin Volatility Extreme Low",
      13168 +         category="chaikin_volatility",
      13169 +         formula_template="""df['hl'] = df['high'] - df['low']
      13170 + df['hl_ema'] = ta.EMA(df['hl'], timeperiod={period})
      13171 + df['chv'] = (df['hl_ema'] - df['hl_ema'].shift({period})) / (df['hl_ema'].shift({period}) + 1e-10) * 100
      13172 + df['low_vol'] = df['chv'] < {threshold}
      13173 + df['entry_signal'] = df['low_vol']""",
      13174 +         params={"period": [10], "threshold": [-20, -30]},
      13175 +         direction="bidi",
      13176 +         lookback=25,
      13177 +         indicators=["EMA"],
      13178 +         combinable_with=["volume", "confirmation"],
      13179 +         strategy_type="CHV",
      13180 +     ),
      13181 +     # Chaikin Vol Expansion
      13182 +     PatternBlock(
      13183 +         id="CHAIKIN_VOL_EXPAND",
      13184 +         name="Chaikin Volatility Expansion",
      13185 +         category="chaikin_volatility",
      13186 +         formula_template="""df['hl'] = df['high'] - df['low']
      13187 + df['hl_ema'] = ta.EMA(df['hl'], timeperiod={period})
      13188 + df['chv'] = (df['hl_ema'] - df['hl_ema'].shift({period})) / (df['hl_ema'].shift({period}) + 1e-10) * 100
      13189 + df['was_low'] = df['chv'].shift(3) < 0
      13190 + df['now_high'] = df['chv'] > {threshold}
      13191 + df['expansion'] = df['was_low'] & df['now_high']
      13192 + df['entry_signal'] = df['expansion']""",
      13193 +         params={"period": [10], "threshold": [10, 20]},
      13194 +         direction="bidi",
      13195 +         lookback=30,
      13196 +         indicators=["EMA"],
      13197 +         combinable_with=["momentum", "confirmation"],
      13198 +         strategy_type="CHV",
      13199 +     ),
      13200 + ]
      13201 +
      13202 +
      13203 + # =============================================================================
      13204 + # HISTORICAL VOLATILITY BLOCKS
      13205 + # =============================================================================
      13206 +
      13207 + HISTORICAL_VOLATILITY_BLOCKS = [
      13208 +     # HV Low (consolidation)
      13209 +     PatternBlock(
      13210 +         id="HV_LOW",
      13211 +         name="Historical Volatility Low",
      13212 +         category="historical_volatility",
      13213 +         formula_template="""df['returns'] = np.log(df['close'] / df['close'].shift(1))
      13214 + df['hv'] = df['returns'].rolling({period}).std() * np.sqrt(252) * 100
      13215 + df['hv_ma'] = df['hv'].rolling({period}).mean()
      13216 + df['low_hv'] = df['hv'] < df['hv_ma'] * {mult}
      13217 + df['entry_signal'] = df['low_hv']""",
      13218 +         params={"period": [20], "mult": [0.7, 0.8]},
      13219 +         direction="bidi",
      13220 +         lookback=40,
      13221 +         indicators=[],
      13222 +         combinable_with=["momentum", "threshold"],
      13223 +         strategy_type="HVO",
      13224 +     ),
      13225 +     # HV Breakout
      13226 +     PatternBlock(
      13227 +         id="HV_BREAKOUT",
      13228 +         name="Historical Volatility Breakout",
      13229 +         category="historical_volatility",
      13230 +         formula_template="""df['returns'] = np.log(df['close'] / df['close'].shift(1))
      13231 + df['hv'] = df['returns'].rolling({period}).std() * np.sqrt(252) * 100
      13232 + df['hv_ma'] = df['hv'].rolling({period}).mean()
      13233 + df['was_low'] = df['hv'].shift(3) < df['hv_ma'].shift(3)
      13234 + df['now_high'] = df['hv'] > df['hv_ma']
      13235 + df['breakout'] = df['was_low'] & df['now_high']
      13236 + df['price_up'] = df['close'] > df['close'].shift(3)
      13237 + df['entry_signal'] = df['breakout'] & df['price_up']""",
      13238 +         params={"period": [20]},
      13239 +         direction="long",
      13240 +         lookback=40,
      13241 +         indicators=[],
      13242 +         combinable_with=["volume", "confirmation"],
      13243 +         strategy_type="HVO",
      13244 +     ),
      13245 +     # HV Rising
      13246 +     PatternBlock(
      13247 +         id="HV_RISING",
      13248 +         name="Historical Volatility Rising",
      13249 +         category="historical_volatility",
      13250 +         formula_template="""df['returns'] = np.log(df['close'] / df['close'].shift(1))
      13251 + df['hv'] = df['returns'].rolling({period}).std() * np.sqrt(252) * 100
      13252 + df['rising'] = df['hv'] > df['hv'].shift(5)
      13253 + df['price_trend'] = df['close'] > df['close'].shift(5)
      13254 + df['entry_signal'] = df['rising'] & df['price_trend']""",
      13255 +         params={"period": [20]},
      13256 +         direction="long",
      13257 +         lookback=35,
      13258 +         indicators=[],
      13259 +         combinable_with=["momentum", "confirmation"],
      13260 +         strategy_type="HVO",
      13261 +     ),
      13262 + ]
      13263 +
      13264 +
      13265 + # =============================================================================
      13266 + # STANDARD ERROR BLOCKS
      13267 + # =============================================================================
      13268 +
      13269 + STANDARD_ERROR_BLOCKS = [
      13270 +     # Standard Error Band Touch
      13271 +     PatternBlock(
      13272 +         id="SE_BAND_TOUCH",
      13273 +         name="Standard Error Band Touch",
      13274 +         category="standard_error",
      13275 +         formula_template="""df['reg'] = ta.LINEARREG(df['close'], timeperiod={period})
      13276 + df['se'] = ta.STDDEV(df['close'], timeperiod={period}) / np.sqrt({period})
      13277 + df['upper'] = df['reg'] + df['se'] * {mult}
      13278 + df['lower'] = df['reg'] - df['se'] * {mult}
      13279 + df['at_lower'] = df['low'] <= df['lower']
      13280 + df['bounce'] = df['close'] > df['open']
      13281 + df['entry_signal'] = df['at_lower'] & df['bounce']""",
      13282 +         params={"period": [20], "mult": [2.0, 2.5]},
      13283 +         direction="long",
      13284 +         lookback=30,
      13285 +         indicators=["LINEARREG", "STDDEV"],
      13286 +         combinable_with=["volume", "confirmation"],
      13287 +         strategy_type="SER",
      13288 +     ),
      13289 +     # Standard Error Cross Up
      13290 +     PatternBlock(
      13291 +         id="SE_CROSS_UP",
      13292 +         name="Standard Error Cross Up",
      13293 +         category="standard_error",
      13294 +         formula_template="""df['reg'] = ta.LINEARREG(df['close'], timeperiod={period})
      13295 + df['cross_up'] = (df['close'] > df['reg']) & (df['close'].shift(1) <= df['reg'].shift(1))
      13296 + df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
      13297 + df['slope_pos'] = df['slope'] > 0
      13298 + df['entry_signal'] = df['cross_up'] & df['slope_pos']""",
      13299 +         params={"period": [20]},
      13300 +         direction="long",
      13301 +         lookback=30,
      13302 +         indicators=["LINEARREG", "LINEARREG_SLOPE"],
      13303 +         combinable_with=["momentum", "threshold"],
      13304 +         strategy_type="SER",
      13305 +     ),
      13306 +     # Standard Error Narrow
      13307 +     PatternBlock(
      13308 +         id="SE_NARROW",
      13309 +         name="Standard Error Narrow",
      13310 +         category="standard_error",
      13311 +         formula_template="""df['se'] = ta.STDDEV(df['close'], timeperiod={period}) / np.sqrt({period})
      13312 + df['se_ma'] = df['se'].rolling({period}).mean()
      13313 + df['narrow'] = df['se'] < df['se_ma'] * {mult}
      13314 + df['narrow_days'] = df['narrow'].rolling(5).sum() >= 3
      13315 + df['entry_signal'] = df['narrow_days']""",
      13316 +         params={"period": [20], "mult": [0.7, 0.8]},
      13317 +         direction="bidi",
      13318 +         lookback=35,
      13319 +         indicators=["STDDEV"],
      13320 +         combinable_with=["volume", "confirmation"],
      13321 +         strategy_type="SER",
      13322 +     ),
      13323 + ]
      13324 +
      13325 +
      13326 + # =============================================================================
      13327 + # REGRESSION SLOPE BLOCKS
      13328 + # =============================================================================
      13329 +
      13330 + REGRESSION_SLOPE_BLOCKS = [
      13331 +     # Slope Positive Strong
      13332 +     PatternBlock(
      13333 +         id="REG_SLOPE_STRONG",
      13334 +         name="Regression Slope Strong",
      13335 +         category="regression_slope",
      13336 +         formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
      13337 + df['slope_norm'] = df['slope'] / df['close'] * 100
      13338 + df['strong'] = df['slope_norm'] > {threshold}
      13339 + df['entry_signal'] = df['strong']""",
      13340 +         params={"period": [14, 20], "threshold": [0.5, 1.0]},
      13341 +         direction="long",
      13342 +         lookback=30,
      13343 +         indicators=["LINEARREG_SLOPE"],
      13344 +         combinable_with=["volume", "momentum"],
      13345 +         strategy_type="RSL",
      13346 +     ),
      13347 +     # Slope Turn Up
      13348 +     PatternBlock(
      13349 +         id="REG_SLOPE_TURN_UP",
      13350 +         name="Regression Slope Turn Up",
      13351 +         category="regression_slope",
      13352 +         formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
      13353 + df['was_neg'] = df['slope'].shift(1) < 0
      13354 + df['now_pos'] = df['slope'] > 0
      13355 + df['turn_up'] = df['was_neg'] & df['now_pos']
      13356 + df['entry_signal'] = df['turn_up']""",
      13357 +         params={"period": [14, 20]},
      13358 +         direction="long",
      13359 +         lookback=30,
      13360 +         indicators=["LINEARREG_SLOPE"],
      13361 +         combinable_with=["confirmation", "threshold"],
      13362 +         strategy_type="RSL",
      13363 +     ),
      13364 +     # Slope Accelerating
      13365 +     PatternBlock(
      13366 +         id="REG_SLOPE_ACCEL",
      13367 +         name="Regression Slope Accelerating",
      13368 +         category="regression_slope",
      13369 +         formula_template="""df['slope'] = ta.LINEARREG_SLOPE(df['close'], timeperiod={period})
      13370 + df['slope_change'] = df['slope'] - df['slope'].shift(3)
      13371 + df['accelerating'] = df['slope_change'] > 0
      13372 + df['positive'] = df['slope'] > 0
      13373 + df['entry_signal'] = df['accelerating'] & df['positive']""",
      13374 +         params={"period": [14]},
      13375 +         direction="long",
      13376 +         lookback=25,
      13377 +         indicators=["LINEARREG_SLOPE"],
      13378 +         combinable_with=["volume", "confirmation"],
      13379 +         strategy_type="RSL",
      13380 +     ),
      13381 + ]
      13382 +
      13383 +
      13384 + # =============================================================================
      13385 + # PRICE OSCILLATOR EXTENDED BLOCKS
      13386 + # =============================================================================
      13387 +
      13388 + PRICE_OSCILLATOR_EXT_BLOCKS = [
      13389 +     # Price Oscillator Cross
      13390 +     PatternBlock(
      13391 +         id="PRICE_OSC_CROSS_EXT",
      13392 +         name="Price Oscillator Cross Extended",
      13393 +         category="price_oscillator_ext",
      13394 +         formula_template="""df['fast_ma'] = ta.EMA(df['close'], timeperiod={fast})
      13395 + df['slow_ma'] = ta.EMA(df['close'], timeperiod={slow})
      13396 + df['po'] = (df['fast_ma'] - df['slow_ma']) / df['slow_ma'] * 100
      13397 + df['po_signal'] = ta.SMA(df['po'], timeperiod=9)
      13398 + df['cross_up'] = (df['po'] > df['po_signal']) & (df['po'].shift(1) <= df['po_signal'].shift(1))
      13399 + df['entry_signal'] = df['cross_up']""",
      13400 +         params={"fast": [10], "slow": [21]},
      13401 +         direction="long",
      13402 +         lookback=35,
      13403 +         indicators=["EMA", "SMA"],
      13404 +         combinable_with=["volume", "momentum"],
      13405 +         strategy_type="POX",
      13406 +     ),
      13407 +     # Price Oscillator Zero Cross
      13408 +     PatternBlock(
      13409 +         id="PRICE_OSC_ZERO_EXT",
      13410 +         name="Price Oscillator Zero Cross",
      13411 +         category="price_oscillator_ext",
      13412 +         formula_template="""df['fast_ma'] = ta.EMA(df['close'], timeperiod={fast})
      13413 + df['slow_ma'] = ta.EMA(df['close'], timeperiod={slow})
      13414 + df['po'] = (df['fast_ma'] - df['slow_ma']) / df['slow_ma'] * 100
      13415 + df['cross_zero'] = (df['po'] > 0) & (df['po'].shift(1) <= 0)
      13416 + df['entry_signal'] = df['cross_zero']""",
      13417 +         params={"fast": [10], "slow": [21]},
      13418 +         direction="long",
      13419 +         lookback=35,
      13420 +         indicators=["EMA"],
      13421 +         combinable_with=["confirmation", "threshold"],
      13422 +         strategy_type="POX",
      13423 +     ),
      13424 +     # Price Oscillator Strong
      13425 +     PatternBlock(
      13426 +         id="PRICE_OSC_STRONG_EXT",
      13427 +         name="Price Oscillator Strong",
      13428 +         category="price_oscillator_ext",
      13429 +         formula_template="""df['fast_ma'] = ta.EMA(df['close'], timeperiod={fast})
      13430 + df['slow_ma'] = ta.EMA(df['close'], timeperiod={slow})
      13431 + df['po'] = (df['fast_ma'] - df['slow_ma']) / df['slow_ma'] * 100
      13432 + df['strong'] = df['po'] > {threshold}
      13433 + df['rising'] = df['po'] > df['po'].shift(3)
      13434 + df['entry_signal'] = df['strong'] & df['rising']""",
      13435 +         params={"fast": [10], "slow": [21], "threshold": [1.0, 2.0]},
      13436 +         direction="long",
      13437 +         lookback=35,
      13438 +         indicators=["EMA"],
      13439 +         combinable_with=["volume", "confirmation"],
      13440 +         strategy_type="POX",
      13441 +     ),
      13442 + ]
      13443 +
      13444 +
      13445 + # =============================================================================
      13446 + # VOLUME OSCILLATOR BLOCKS
      13447 + # =============================================================================
      13448 +
      13449 + VOLUME_OSCILLATOR_BLOCKS = [
      13450 +     # Volume Oscillator Positive
      13451 +     PatternBlock(
      13452 +         id="VOL_OSC_POSITIVE",
      13453 +         name="Volume Oscillator Positive",
      13454 +         category="volume_oscillator",
      13455 +         formula_template="""df['fast_vol'] = ta.SMA(df['volume'], timeperiod={fast})
      13456 + df['slow_vol'] = ta.SMA(df['volume'], timeperiod={slow})
      13457 + df['vo'] = (df['fast_vol'] - df['slow_vol']) / df['slow_vol'] * 100
      13458 + df['positive'] = df['vo'] > 0
      13459 + df['rising'] = df['vo'] > df['vo'].shift(1)
      13460 + df['price_up'] = df['close'] > df['close'].shift(1)
      13461 + df['entry_signal'] = df['positive'] & df['rising'] & df['price_up']""",
      13462 +         params={"fast": [5], "slow": [20]},
      13463 +         direction="long",
      13464 +         lookback=30,
      13465 +         indicators=["SMA"],
      13466 +         combinable_with=["momentum", "threshold"],
      13467 +         strategy_type="VOO",
      13468 +     ),
      13469 +     # Volume Oscillator Cross
      13470 +     PatternBlock(
      13471 +         id="VOL_OSC_CROSS",
      13472 +         name="Volume Oscillator Cross",
      13473 +         category="volume_oscillator",
      13474 +         formula_template="""df['fast_vol'] = ta.SMA(df['volume'], timeperiod={fast})
      13475 + df['slow_vol'] = ta.SMA(df['volume'], timeperiod={slow})
      13476 + df['vo'] = (df['fast_vol'] - df['slow_vol']) / df['slow_vol'] * 100
      13477 + df['cross_up'] = (df['vo'] > 0) & (df['vo'].shift(1) <= 0)
      13478 + df['price_up'] = df['close'] > df['open']
      13479 + df['entry_signal'] = df['cross_up'] & df['price_up']""",
      13480 +         params={"fast": [5], "slow": [20]},
      13481 +         direction="long",
      13482 +         lookback=30,
      13483 +         indicators=["SMA"],
      13484 +         combinable_with=["volume", "confirmation"],
      13485 +         strategy_type="VOO",
      13486 +     ),
      13487 +     # Volume Oscillator Strong
      13488 +     PatternBlock(
      13489 +         id="VOL_OSC_STRONG",
      13490 +         name="Volume Oscillator Strong",
      13491 +         category="volume_oscillator",
      13492 +         formula_template="""df['fast_vol'] = ta.SMA(df['volume'], timeperiod={fast})
      13493 + df['slow_vol'] = ta.SMA(df['volume'], timeperiod={slow})
      13494 + df['vo'] = (df['fast_vol'] - df['slow_vol']) / df['slow_vol'] * 100
      13495 + df['strong'] = df['vo'] > {threshold}
      13496 + df['entry_signal'] = df['strong']""",
      13497 +         params={"fast": [5], "slow": [20], "threshold": [30, 50]},
      13498 +         direction="bidi",
      13499 +         lookback=30,
      13500 +         indicators=["SMA"],
      13501 +         combinable_with=["momentum", "confirmation"],
      13502 +         strategy_type="VOO",
      13503 +     ),
      13504 + ]
      13505 +
      13506 +
      13507 + # =============================================================================
      13508 + # MOMENTUM PERCENTILE BLOCKS
      13509 + # =============================================================================
      13510 +
      13511 + MOMENTUM_PERCENTILE_BLOCKS = [
      13512 +     # Momentum Percentile Low
      13513 +     PatternBlock(
      13514 +         id="MOM_PERCENTILE_LOW",
      13515 +         name="Momentum Percentile Low",
      13516 +         category="momentum_percentile",
      13517 +         formula_template="""df['mom'] = df['close'] - df['close'].shift({mom_period})
      13518 + df['percentile'] = df['mom'].rolling({lookback}).apply(lambda x: (x < x.iloc[-1]).sum() / len(x) * 100, raw=False)
      13519 + df['low_pct'] = df['percentile'] < {level}
      13520 + df['entry_signal'] = df['low_pct']""",
      13521 +         params={"mom_period": [10], "lookback": [100], "level": [20, 25]},
      13522 +         direction="long",
      13523 +         lookback=120,
      13524 +         indicators=[],
      13525 +         combinable_with=["volume", "confirmation"],
      13526 +         strategy_type="MPT",
      13527 +     ),
      13528 +     # Momentum Percentile Rising
      13529 +     PatternBlock(
      13530 +         id="MOM_PERCENTILE_RISING",
      13531 +         name="Momentum Percentile Rising",
      13532 +         category="momentum_percentile",
      13533 +         formula_template="""df['mom'] = df['close'] - df['close'].shift({mom_period})
      13534 + df['percentile'] = df['mom'].rolling({lookback}).apply(lambda x: (x < x.iloc[-1]).sum() / len(x) * 100, raw=False)
      13535 + df['rising'] = df['percentile'] > df['percentile'].shift(5)
      13536 + df['above_mid'] = df['percentile'] > 50
      13537 + df['entry_signal'] = df['rising'] & df['above_mid']""",
      13538 +         params={"mom_period": [10], "lookback": [100]},
      13539 +         direction="long",
      13540 +         lookback=120,
      13541 +         indicators=[],
      13542 +         combinable_with=["momentum", "threshold"],
      13543 +         strategy_type="MPT",
      13544 +     ),
      13545 +     # Momentum Percentile Extreme High
      13546 +     PatternBlock(
      13547 +         id="MOM_PERCENTILE_HIGH",
      13548 +         name="Momentum Percentile High",
      13549 +         category="momentum_percentile",
      13550 +         formula_template="""df['mom'] = df['close'] - df['close'].shift({mom_period})
      13551 + df['percentile'] = df['mom'].rolling({lookback}).apply(lambda x: (x < x.iloc[-1]).sum() / len(x) * 100, raw=False)
      13552 + df['high_pct'] = df['percentile'] > {level}
      13553 + df['entry_signal'] = df['high_pct']""",
      13554 +         params={"mom_period": [10], "lookback": [100], "level": [75, 80]},
      13555 +         direction="long",
      13556 +         lookback=120,
      13557 +         indicators=[],
      13558 +         combinable_with=["volume", "confirmation"],
      13559 +         strategy_type="MPT",
      13560 +     ),
      13561 + ]
      13562 +
      13563 +
      13564 + # =============================================================================
      13565 + # TREND SCORE BLOCKS
      13566 + # =============================================================================
      13567 +
      13568 + TREND_SCORE_BLOCKS = [
      13569 +     # Trend Score Bullish
      13570 +     PatternBlock(
      13571 +         id="TREND_SCORE_BULL",
      13572 +         name="Trend Score Bullish",
      13573 +         category="trend_score",
      13574 +         formula_template="""df['ma5'] = ta.SMA(df['close'], timeperiod=5)
      13575 + df['ma10'] = ta.SMA(df['close'], timeperiod=10)
      13576 + df['ma20'] = ta.SMA(df['close'], timeperiod=20)
      13577 + df['score'] = (df['close'] > df['ma5']).astype(int) + (df['ma5'] > df['ma10']).astype(int) + (df['ma10'] > df['ma20']).astype(int)
            + + (df['close'] > df['ma20']).astype(int)
      13578 + df['bullish'] = df['score'] >= {threshold}
      13579 + df['entry_signal'] = df['bullish']""",
      13580 +         params={"threshold": [3, 4]},
      13581 +         direction="long",
      13582 +         lookback=30,
      13583 +         indicators=["SMA"],
      13584 +         combinable_with=["volume", "momentum"],
      13585 +         strategy_type="TSC",
      13586 +     ),
      13587 +     # Trend Score Improving
      13588 +     PatternBlock(
      13589 +         id="TREND_SCORE_IMPROVE",
      13590 +         name="Trend Score Improving",
      13591 +         category="trend_score",
      13592 +         formula_template="""df['ma5'] = ta.SMA(df['close'], timeperiod=5)
      13593 + df['ma10'] = ta.SMA(df['close'], timeperiod=10)
      13594 + df['ma20'] = ta.SMA(df['close'], timeperiod=20)
      13595 + df['score'] = (df['close'] > df['ma5']).astype(int) + (df['ma5'] > df['ma10']).astype(int) + (df['ma10'] > df['ma20']).astype(int)
            + + (df['close'] > df['ma20']).astype(int)
      13596 + df['improving'] = df['score'] > df['score'].shift(3)
      13597 + df['above_mid'] = df['score'] >= 2
      13598 + df['entry_signal'] = df['improving'] & df['above_mid']""",
      13599 +         params={},
      13600 +         direction="long",
      13601 +         lookback=30,
      13602 +         indicators=["SMA"],
      13603 +         combinable_with=["confirmation", "threshold"],
      13604 +         strategy_type="TSC",
      13605 +     ),
      13606 +     # Trend Score Flip
      13607 +     PatternBlock(
      13608 +         id="TREND_SCORE_FLIP",
      13609 +         name="Trend Score Flip Bullish",
      13610 +         category="trend_score",
      13611 +         formula_template="""df['ma5'] = ta.SMA(df['close'], timeperiod=5)
      13612 + df['ma10'] = ta.SMA(df['close'], timeperiod=10)
      13613 + df['ma20'] = ta.SMA(df['close'], timeperiod=20)
      13614 + df['score'] = (df['close'] > df['ma5']).astype(int) + (df['ma5'] > df['ma10']).astype(int) + (df['ma10'] > df['ma20']).astype(int)
            + + (df['close'] > df['ma20']).astype(int)
      13615 + df['was_bearish'] = df['score'].shift(1) <= 1
      13616 + df['now_bullish'] = df['score'] >= 3
      13617 + df['flip'] = df['was_bearish'] & df['now_bullish']
      13618 + df['entry_signal'] = df['flip']""",
      13619 +         params={},
      13620 +         direction="long",
      13621 +         lookback=30,
      13622 +         indicators=["SMA"],
      13623 +         combinable_with=["volume", "confirmation"],
      13624 +         strategy_type="TSC",
      13625 +     ),
      13626 + ]
      13627 +
      13628 +
      13629 + # =============================================================================
      13630 + # ADAPTIVE RSI BLOCKS
      13631 + # =============================================================================
      13632 +
      13633 + ADAPTIVE_RSI_BLOCKS = [
      13634 +     # Adaptive RSI Oversold
      13635 +     PatternBlock(
      13636 +         id="ARSI_OVERSOLD",
      13637 +         name="Adaptive RSI Oversold",
      13638 +         category="adaptive_rsi",
      13639 +         formula_template="""df['vol'] = df['close'].rolling(10).std()
      13640 + df['vol_ratio'] = df['vol'] / df['vol'].rolling(50).mean()
      13641 + df['dyn_period'] = np.clip(14 / df['vol_ratio'], 7, 28).fillna(14).astype(int)
      13642 + df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      13643 + df['dyn_oversold'] = {base_level} - (df['vol_ratio'] - 1) * 10
      13644 + df['dyn_oversold'] = df['dyn_oversold'].clip(20, 40)
      13645 + df['oversold'] = df['rsi'] < df['dyn_oversold']
      13646 + df['entry_signal'] = df['oversold']""",
      13647 +         params={"base_level": [30, 35]},
      13648 +         direction="long",
      13649 +         lookback=60,
      13650 +         indicators=["RSI"],
      13651 +         combinable_with=["volume", "confirmation"],
      13652 +         strategy_type="ARS",
      13653 +     ),
      13654 +     # Adaptive RSI Cross
      13655 +     PatternBlock(
      13656 +         id="ARSI_CROSS",
      13657 +         name="Adaptive RSI Cross",
      13658 +         category="adaptive_rsi",
      13659 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      13660 + df['rsi_ma'] = ta.EMA(df['rsi'], timeperiod=9)
      13661 + df['vol'] = df['close'].rolling(10).std()
      13662 + df['vol_high'] = df['vol'] > df['vol'].rolling(20).mean()
      13663 + df['cross_up'] = (df['rsi'] > df['rsi_ma']) & (df['rsi'].shift(1) <= df['rsi_ma'].shift(1))
      13664 + df['entry_signal'] = df['cross_up'] & df['vol_high']""",
      13665 +         params={},
      13666 +         direction="long",
      13667 +         lookback=40,
      13668 +         indicators=["RSI", "EMA"],
      13669 +         combinable_with=["momentum", "threshold"],
      13670 +         strategy_type="ARS",
      13671 +     ),
      13672 +     # Adaptive RSI Strong
      13673 +     PatternBlock(
      13674 +         id="ARSI_STRONG",
      13675 +         name="Adaptive RSI Strong",
      13676 +         category="adaptive_rsi",
      13677 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      13678 + df['vol'] = df['close'].rolling(10).std()
      13679 + df['vol_ratio'] = df['vol'] / df['vol'].rolling(50).mean()
      13680 + df['dyn_strong'] = {base_level} + (df['vol_ratio'] - 1) * 10
      13681 + df['dyn_strong'] = df['dyn_strong'].clip(55, 75)
      13682 + df['strong'] = df['rsi'] > df['dyn_strong']
      13683 + df['rising'] = df['rsi'] > df['rsi'].shift(3)
      13684 + df['entry_signal'] = df['strong'] & df['rising']""",
      13685 +         params={"base_level": [60, 65]},
      13686 +         direction="long",
      13687 +         lookback=60,
      13688 +         indicators=["RSI"],
      13689 +         combinable_with=["volume", "confirmation"],
      13690 +         strategy_type="ARS",
      13691 +     ),
      13692 + ]
      13693 +
      13694 +
      13695 + # =============================================================================
      13696   # ALL BLOCKS COMBINED
      13697   # =============================================================================
      13698

 ▐▛███▜▌   Claude Code v2.1.5
▝▜█████▛▘  Opus 4.5 · Claude Max
  ▘▘ ▝▝    ~/sixbtc
══════════════════════════════════════════════════════ Conversation compacted · ctrl+o for history ═════════════════════════════════════════════════════
  ⎿  Referenced file src/generator/pattern_gen/building_blocks.py
  ⎿  Read src/generator/pattern_gen/templates/pattern_gen_strategy.j2 (97 lines)
  ⎿  Read src/generator/pattern_gen/generator.py (449 lines)
  ⎿  Read src/validator/syntax_validator.py (222 lines)
  ⎿  Read src/config/loader.py (325 lines)
  ⎿  Todo list read (11 items)

● Continuo con Round 19. Devo aggiornare ALL_BLOCKS per includere i 10 nuovi gruppi di blocchi appena aggiunti.

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 200 lines

● Search(pattern: "^ALL_BLOCKS = ", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 200 lines

● Devo aggiungere i 10 nuovi gruppi di blocchi a ALL_BLOCKS.

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      13881       + MARKET_FACILITATION_BLOCKS
      13882       + VOLATILITY_SYSTEM_BLOCKS
      13883       + PRICE_CHANNEL_EXT_BLOCKS
      13884 +     + BALANCE_OF_POWER_EXT_BLOCKS
      13885 +     + CHAIKIN_VOLATILITY_BLOCKS
      13886 +     + HISTORICAL_VOLATILITY_BLOCKS
      13887 +     + STANDARD_ERROR_BLOCKS
      13888 +     + REGRESSION_SLOPE_BLOCKS
      13889 +     + PRICE_OSCILLATOR_EXT_BLOCKS
      13890 +     + VOLUME_OSCILLATOR_BLOCKS
      13891 +     + MOMENTUM_PERCENTILE_BLOCKS
      13892 +     + TREND_SCORE_BLOCKS
      13893 +     + ADAPTIVE_RSI_BLOCKS
      13894   )
      13895
      13896   # Index by ID for quick lookup

● Eseguo il test di validazione per tutti i blocchi.

● Bash(source .venv/bin/activate && python3 << 'EOF'
      import sys…)
  ⎿  Total blocks: 688
     Categories: 193
     … +34 lines (ctrl+o to expand)

● Round 19 completato!

  Risultati:
  - Blocchi totali: 688 (+30 nuovi)
  - Categorie: 193
  - Tipi strategia: 182
  - Validazione: 200/200 strategie valide
  - Lookahead: Nessun pattern rilevato
  - Strategie stimate: ~135,824

  Nuovi blocchi aggiunti (Round 19):
  1. BALANCE_OF_POWER_EXT_BLOCKS (BPX): 3 blocchi - divergence/extreme/confirmation patterns
  2. CHAIKIN_VOLATILITY_BLOCKS (CHV): 3 blocchi - expansion/spike/compression volatility
  3. HISTORICAL_VOLATILITY_BLOCKS (HVO): 3 blocchi - low/breakout/rising volatility
  4. STANDARD_ERROR_BLOCKS (SER): 3 blocchi - band touch/cross/narrow patterns
  5. REGRESSION_SLOPE_BLOCKS (RSL): 3 blocchi - strong/turn up/accelerating slopes
  6. PRICE_OSCILLATOR_EXT_BLOCKS (POX): 3 blocchi - cross/divergence/zero line
  7. VOLUME_OSCILLATOR_BLOCKS (VOO): 3 blocchi - cross/surge/divergence patterns
  8. MOMENTUM_PERCENTILE_BLOCKS (MPT): 3 blocchi - extreme/reversal/expansion patterns
  9. TREND_SCORE_BLOCKS (TSC): 3 blocchi - strong/improving/extreme scores
  10. ADAPTIVE_RSI_BLOCKS (ARS): 3 blocchi - oversold/overbought/reversal con RSI dinamico

  Progressione sessione:
  ┌─────────────┬─────────┬───────────────────┐
  │    Round    │ Blocchi │ Strategie stimate │
  ├─────────────┼─────────┼───────────────────┤
  │ 11 (inizio) │ 447     │ ~100,392          │
  ├─────────────┼─────────┼───────────────────┤
  │ 12          │ 478     │ ~105,288          │
  ├─────────────┼─────────┼───────────────────┤
  │ 13          │ 508     │ ~109,672          │
  ├─────────────┼─────────┼───────────────────┤
  │ 14          │ 538     │ ~114,024          │
  ├─────────────┼─────────┼───────────────────┤
  │ 15          │ 568     │ ~118,312          │
  ├─────────────┼─────────┼───────────────────┤
  │ 16          │ 598     │ ~122,784          │
  ├─────────────┼─────────┼───────────────────┤
  │ 17          │ 628     │ ~127,096          │
  ├─────────────┼─────────┼───────────────────┤
  │ 18          │ 658     │ ~131,432          │
  ├─────────────┼─────────┼───────────────────┤
  │ 19          │ 688     │ ~135,824          │
  └─────────────┴─────────┴───────────────────┘
  Hai testato che tutto funzioni? Altre possibili migliorie? (stessi requisiti: no modifiche al codice esistente, piena compatibilita, no diminuzione strategie)

✻ Crunched for 3m 36s

❯ hai testato che tutto funzioni?
  altre possibili migliorie? con gli stessi requisiti, cioè no modifiche al codice esistente, piena compatibilità, no diminuzione strategie
  dimmi solo

● Test Round 19: PASSATO
  - 200/200 strategie valide
  - 0 errori lookahead
  - 688 blocchi funzionanti

  ---
  Proposta Round 20 - 10 nuove categorie (30 blocchi):

  1. RATE_OF_CHANGE_EXT_BLOCKS (RCX): ROC smoothed, ROC percentile, ROC acceleration
  2. VOLATILITY_BREAKOUT_BLOCKS (VBK): ATR expansion trigger, volatility squeeze break, range breakout
  3. PRICE_DENSITY_BLOCKS (PDN): Price clustering, consolidation density, distribution width
  4. MOMENTUM_DIVERGENCE_EXT_BLOCKS (MDV): Multi-indicator divergence, hidden divergence, triple divergence
  5. TREND_CONFIRMATION_BLOCKS (TCF): Multi-MA alignment, ADX + DI confirm, trend unanimity
  6. OSCILLATOR_EXTREME_BLOCKS (OEX): RSI + Stoch extreme, multi-osc oversold, oscillator unanimity
  7. VOLUME_MOMENTUM_BLOCKS (VMM): Volume ROC, volume acceleration, volume momentum divergence
  8. CANDLE_MOMENTUM_BLOCKS (CDM): Body momentum, candle acceleration, consecutive body growth
  9. SUPPORT_BOUNCE_BLOCKS (SBN): Dynamic support test, pivot bounce, MA support touch
  10. BREAKOUT_STRENGTH_BLOCKS (BKS): Volume-confirmed break, ATR break magnitude, multi-bar break

  Risultato atteso:
  - Blocchi: 688 → 718 (+30)
  - Strategie: ~135,824 → ~140,000+

  Vuoi procedere?

❯ si

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 60 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 622 lines
      13693
      13694
      13695   # =============================================================================
      13696 + # RATE OF CHANGE EXTENDED BLOCKS
      13697 + # =============================================================================
      13698 +
      13699 + RATE_OF_CHANGE_EXT_BLOCKS = [
      13700 +     # ROC Smoothed Cross
      13701 +     PatternBlock(
      13702 +         id="ROC_SMOOTHED_CROSS",
      13703 +         name="ROC Smoothed Cross",
      13704 +         category="rate_of_change_ext",
      13705 +         formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
      13706 + df['roc_smooth'] = ta.EMA(df['roc'], timeperiod=5)
      13707 + df['roc_signal'] = ta.EMA(df['roc_smooth'], timeperiod=9)
      13708 + df['cross_up'] = (df['roc_smooth'] > df['roc_signal']) & (df['roc_smooth'].shift(1) <= df['roc_signal'].shift(1))
      13709 + df['entry_signal'] = df['cross_up']""",
      13710 +         params={"period": [10, 14]},
      13711 +         direction="long",
      13712 +         lookback=30,
      13713 +         indicators=["ROC", "EMA"],
      13714 +         combinable_with=["volume", "confirmation"],
      13715 +         strategy_type="RCX",
      13716 +     ),
      13717 +     # ROC Percentile Extreme
      13718 +     PatternBlock(
      13719 +         id="ROC_PERCENTILE",
      13720 +         name="ROC Percentile Extreme",
      13721 +         category="rate_of_change_ext",
      13722 +         formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
      13723 + df['roc_pct'] = df['roc'].rolling(100).apply(lambda x: (x.iloc[-1] > x).sum() / len(x) * 100, raw=False)
      13724 + df['extreme_low'] = df['roc_pct'] < {threshold}
      13725 + df['turning'] = df['roc'] > df['roc'].shift(1)
      13726 + df['entry_signal'] = df['extreme_low'] & df['turning']""",
      13727 +         params={"period": [10], "threshold": [10, 20]},
      13728 +         direction="long",
      13729 +         lookback=120,
      13730 +         indicators=["ROC"],
      13731 +         combinable_with=["volume", "threshold"],
      13732 +         strategy_type="RCX",
      13733 +     ),
      13734 +     # ROC Acceleration
      13735 +     PatternBlock(
      13736 +         id="ROC_ACCELERATION",
      13737 +         name="ROC Acceleration",
      13738 +         category="rate_of_change_ext",
      13739 +         formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
      13740 + df['roc_change'] = df['roc'] - df['roc'].shift(3)
      13741 + df['accelerating'] = df['roc_change'] > 0
      13742 + df['positive'] = df['roc'] > 0
      13743 + df['entry_signal'] = df['accelerating'] & df['positive']""",
      13744 +         params={"period": [10, 14]},
      13745 +         direction="long",
      13746 +         lookback=25,
      13747 +         indicators=["ROC"],
      13748 +         combinable_with=["momentum", "confirmation"],
      13749 +         strategy_type="RCX",
      13750 +     ),
      13751 + ]
      13752 +
      13753 +
      13754 + # =============================================================================
      13755 + # VOLATILITY BREAKOUT BLOCKS
      13756 + # =============================================================================
      13757 +
      13758 + VOLATILITY_BREAKOUT_BLOCKS = [
      13759 +     # ATR Expansion Trigger
      13760 +     PatternBlock(
      13761 +         id="ATR_EXPANSION_TRIGGER",
      13762 +         name="ATR Expansion Trigger",
      13763 +         category="volatility_breakout",
      13764 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
      13765 + df['atr_ma'] = df['atr'].rolling(20).mean()
      13766 + df['was_low'] = df['atr'].shift(3) < df['atr_ma'].shift(3) * {contract_mult}
      13767 + df['now_high'] = df['atr'] > df['atr_ma'] * {expand_mult}
      13768 + df['expansion'] = df['was_low'] & df['now_high']
      13769 + df['price_up'] = df['close'] > df['close'].shift(3)
      13770 + df['entry_signal'] = df['expansion'] & df['price_up']""",
      13771 +         params={"contract_mult": [0.8], "expand_mult": [1.2, 1.5]},
      13772 +         direction="long",
      13773 +         lookback=35,
      13774 +         indicators=["ATR"],
      13775 +         combinable_with=["momentum", "confirmation"],
      13776 +         strategy_type="VBK",
      13777 +     ),
      13778 +     # Volatility Squeeze Break
      13779 +     PatternBlock(
      13780 +         id="VOL_SQUEEZE_BREAK",
      13781 +         name="Volatility Squeeze Break",
      13782 +         category="volatility_breakout",
      13783 +         formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2,
            +nbdevdn=2)
      13784 + df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
      13785 + df['bb_narrow'] = df['bb_width'] < df['bb_width'].rolling(50).quantile(0.2)
      13786 + df['squeeze_days'] = df['bb_narrow'].rolling(5).sum() >= 3
      13787 + df['break_up'] = df['close'] > df['bb_upper']
      13788 + df['entry_signal'] = df['squeeze_days'].shift(1) & df['break_up']""",
      13789 +         params={},
      13790 +         direction="long",
      13791 +         lookback=60,
      13792 +         indicators=["BBANDS"],
      13793 +         combinable_with=["volume", "momentum"],
      13794 +         strategy_type="VBK",
      13795 +     ),
      13796 +     # Range Breakout
      13797 +     PatternBlock(
      13798 +         id="RANGE_BREAKOUT",
      13799 +         name="Range Breakout",
      13800 +         category="volatility_breakout",
      13801 +         formula_template="""df['range'] = df['high'] - df['low']
      13802 + df['avg_range'] = df['range'].rolling({period}).mean()
      13803 + df['narrow_range'] = df['range'] < df['avg_range'] * {mult}
      13804 + df['nr_days'] = df['narrow_range'].rolling(5).sum() >= 3
      13805 + df['high_break'] = df['close'] > df['high'].shift(1).rolling(5).max()
      13806 + df['entry_signal'] = df['nr_days'].shift(1) & df['high_break']""",
      13807 +         params={"period": [20], "mult": [0.6, 0.7]},
      13808 +         direction="long",
      13809 +         lookback=35,
      13810 +         indicators=[],
      13811 +         combinable_with=["volume", "confirmation"],
      13812 +         strategy_type="VBK",
      13813 +     ),
      13814 + ]
      13815 +
      13816 +
      13817 + # =============================================================================
      13818 + # PRICE DENSITY BLOCKS
      13819 + # =============================================================================
      13820 +
      13821 + PRICE_DENSITY_BLOCKS = [
      13822 +     # Price Clustering
      13823 +     PatternBlock(
      13824 +         id="PRICE_CLUSTERING",
      13825 +         name="Price Clustering",
      13826 +         category="price_density",
      13827 +         formula_template="""df['range'] = df['high'].rolling({period}).max() - df['low'].rolling({period}).min()
      13828 + df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
      13829 + df['density'] = df['range'] / (df['atr'] * {period})
      13830 + df['tight'] = df['density'] < {threshold}
      13831 + df['break_up'] = df['close'] > df['high'].shift(1).rolling(5).max()
      13832 + df['entry_signal'] = df['tight'].shift(1) & df['break_up']""",
      13833 +         params={"period": [10], "threshold": [1.5, 2.0]},
      13834 +         direction="long",
      13835 +         lookback=30,
      13836 +         indicators=["ATR"],
      13837 +         combinable_with=["volume", "momentum"],
      13838 +         strategy_type="PDN",
      13839 +     ),
      13840 +     # Consolidation Density
      13841 +     PatternBlock(
      13842 +         id="CONSOLIDATION_DENSITY",
      13843 +         name="Consolidation Density",
      13844 +         category="price_density",
      13845 +         formula_template="""df['hl_range'] = df['high'] - df['low']
      13846 + df['avg_range'] = df['hl_range'].rolling(20).mean()
      13847 + df['small_range'] = df['hl_range'] < df['avg_range'] * {mult}
      13848 + df['consol_days'] = df['small_range'].rolling({period}).sum()
      13849 + df['tight_consol'] = df['consol_days'] >= {period} * 0.7
      13850 + df['breakout'] = df['close'] > df['close'].shift(1).rolling(5).max()
      13851 + df['entry_signal'] = df['tight_consol'].shift(1) & df['breakout']""",
      13852 +         params={"period": [10], "mult": [0.7, 0.8]},
      13853 +         direction="long",
      13854 +         lookback=35,
      13855 +         indicators=[],
      13856 +         combinable_with=["volume", "confirmation"],
      13857 +         strategy_type="PDN",
      13858 +     ),
      13859 +     # Distribution Width
      13860 +     PatternBlock(
      13861 +         id="DISTRIBUTION_WIDTH",
      13862 +         name="Distribution Width",
      13863 +         category="price_density",
      13864 +         formula_template="""df['std'] = df['close'].rolling({period}).std()
      13865 + df['std_norm'] = df['std'] / df['close'] * 100
      13866 + df['narrow'] = df['std_norm'] < df['std_norm'].rolling(50).quantile(0.25)
      13867 + df['expanding'] = df['std_norm'] > df['std_norm'].shift(3)
      13868 + df['entry_signal'] = df['narrow'].shift(3) & df['expanding']""",
      13869 +         params={"period": [20]},
      13870 +         direction="bidi",
      13871 +         lookback=60,
      13872 +         indicators=[],
      13873 +         combinable_with=["momentum", "threshold"],
      13874 +         strategy_type="PDN",
      13875 +     ),
      13876 + ]
      13877 +
      13878 +
      13879 + # =============================================================================
      13880 + # MOMENTUM DIVERGENCE EXTENDED BLOCKS
      13881 + # =============================================================================
      13882 +
      13883 + MOMENTUM_DIVERGENCE_EXT_BLOCKS = [
      13884 +     # Multi-Indicator Divergence
      13885 +     PatternBlock(
      13886 +         id="MULTI_IND_DIV",
      13887 +         name="Multi-Indicator Divergence",
      13888 +         category="momentum_divergence_ext",
      13889 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      13890 + df['macd'], df['macd_signal'], df['macd_hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
      13891 + df['price_lower'] = df['close'] < df['close'].shift({period})
      13892 + df['rsi_higher'] = df['rsi'] > df['rsi'].shift({period})
      13893 + df['macd_higher'] = df['macd_hist'] > df['macd_hist'].shift({period})
      13894 + df['bullish_div'] = df['price_lower'] & df['rsi_higher'] & df['macd_higher']
      13895 + df['entry_signal'] = df['bullish_div']""",
      13896 +         params={"period": [10, 14]},
      13897 +         direction="long",
      13898 +         lookback=30,
      13899 +         indicators=["RSI", "MACD"],
      13900 +         combinable_with=["volume", "confirmation"],
      13901 +         strategy_type="MDV",
      13902 +     ),
      13903 +     # Hidden Divergence
      13904 +     PatternBlock(
      13905 +         id="HIDDEN_DIV",
      13906 +         name="Hidden Divergence",
      13907 +         category="momentum_divergence_ext",
      13908 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      13909 + df['price_higher'] = df['low'] > df['low'].shift({period})
      13910 + df['rsi_lower'] = df['rsi'] < df['rsi'].shift({period})
      13911 + df['uptrend'] = df['close'] > ta.EMA(df['close'], timeperiod=50)
      13912 + df['hidden_bull'] = df['price_higher'] & df['rsi_lower'] & df['uptrend']
      13913 + df['entry_signal'] = df['hidden_bull']""",
      13914 +         params={"period": [10, 14]},
      13915 +         direction="long",
      13916 +         lookback=60,
      13917 +         indicators=["RSI", "EMA"],
      13918 +         combinable_with=["momentum", "confirmation"],
      13919 +         strategy_type="MDV",
      13920 +     ),
      13921 +     # Triple Divergence
      13922 +     PatternBlock(
      13923 +         id="TRIPLE_DIV",
      13924 +         name="Triple Divergence",
      13925 +         category="momentum_divergence_ext",
      13926 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      13927 + df['stoch_k'], df['stoch_d'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
      13928 + df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=14)
      13929 + df['price_low'] = df['close'] < df['close'].shift(10)
      13930 + df['rsi_up'] = df['rsi'] > df['rsi'].shift(10)
      13931 + df['stoch_up'] = df['stoch_k'] > df['stoch_k'].shift(10)
      13932 + df['cci_up'] = df['cci'] > df['cci'].shift(10)
      13933 + df['triple'] = df['price_low'] & df['rsi_up'] & df['stoch_up'] & df['cci_up']
      13934 + df['entry_signal'] = df['triple']""",
      13935 +         params={},
      13936 +         direction="long",
      13937 +         lookback=30,
      13938 +         indicators=["RSI", "STOCH", "CCI"],
      13939 +         combinable_with=["volume", "confirmation"],
      13940 +         strategy_type="MDV",
      13941 +     ),
      13942 + ]
      13943 +
      13944 +
      13945 + # =============================================================================
      13946 + # TREND CONFIRMATION BLOCKS
      13947 + # =============================================================================
      13948 +
      13949 + TREND_CONFIRMATION_BLOCKS = [
      13950 +     # Multi-MA Alignment
      13951 +     PatternBlock(
      13952 +         id="MULTI_MA_ALIGN",
      13953 +         name="Multi-MA Alignment",
      13954 +         category="trend_confirmation",
      13955 +         formula_template="""df['ema10'] = ta.EMA(df['close'], timeperiod=10)
      13956 + df['ema20'] = ta.EMA(df['close'], timeperiod=20)
      13957 + df['ema50'] = ta.EMA(df['close'], timeperiod=50)
      13958 + df['aligned'] = (df['ema10'] > df['ema20']) & (df['ema20'] > df['ema50'])
      13959 + df['price_above'] = df['close'] > df['ema10']
      13960 + df['entry_signal'] = df['aligned'] & df['price_above']""",
      13961 +         params={},
      13962 +         direction="long",
      13963 +         lookback=60,
      13964 +         indicators=["EMA"],
      13965 +         combinable_with=["momentum", "volume"],
      13966 +         strategy_type="TCF",
      13967 +     ),
      13968 +     # ADX + DI Confirm
      13969 +     PatternBlock(
      13970 +         id="ADX_DI_CONFIRM",
      13971 +         name="ADX + DI Confirm",
      13972 +         category="trend_confirmation",
      13973 +         formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
      13974 + df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
      13975 + df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
      13976 + df['strong_trend'] = df['adx'] > {adx_thresh}
      13977 + df['bullish'] = df['plus_di'] > df['minus_di']
      13978 + df['di_strong'] = df['plus_di'] > {di_thresh}
      13979 + df['entry_signal'] = df['strong_trend'] & df['bullish'] & df['di_strong']""",
      13980 +         params={"adx_thresh": [25, 30], "di_thresh": [20, 25]},
      13981 +         direction="long",
      13982 +         lookback=25,
      13983 +         indicators=["ADX", "PLUS_DI", "MINUS_DI"],
      13984 +         combinable_with=["momentum", "confirmation"],
      13985 +         strategy_type="TCF",
      13986 +     ),
      13987 +     # Trend Unanimity
      13988 +     PatternBlock(
      13989 +         id="TREND_UNANIMITY",
      13990 +         name="Trend Unanimity",
      13991 +         category="trend_confirmation",
      13992 +         formula_template="""df['above_sma20'] = df['close'] > ta.SMA(df['close'], timeperiod=20)
      13993 + df['above_sma50'] = df['close'] > ta.SMA(df['close'], timeperiod=50)
      13994 + df['rsi_bullish'] = ta.RSI(df['close'], timeperiod=14) > 50
      13995 + df['macd'], _, _ = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
      13996 + df['macd_pos'] = df['macd'] > 0
      13997 + df['unanimity'] = df['above_sma20'] & df['above_sma50'] & df['rsi_bullish'] & df['macd_pos']
      13998 + df['entry_signal'] = df['unanimity']""",
      13999 +         params={},
      14000 +         direction="long",
      14001 +         lookback=60,
      14002 +         indicators=["SMA", "RSI", "MACD"],
      14003 +         combinable_with=["volume", "threshold"],
      14004 +         strategy_type="TCF",
      14005 +     ),
      14006 + ]
      14007 +
      14008 +
      14009 + # =============================================================================
      14010 + # OSCILLATOR EXTREME BLOCKS
      14011 + # =============================================================================
      14012 +
      14013 + OSCILLATOR_EXTREME_BLOCKS = [
      14014 +     # RSI + Stoch Extreme
      14015 +     PatternBlock(
      14016 +         id="RSI_STOCH_EXTREME",
      14017 +         name="RSI + Stoch Extreme",
      14018 +         category="oscillator_extreme",
      14019 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      14020 + df['stoch_k'], _ = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
      14021 + df['rsi_oversold'] = df['rsi'] < {rsi_level}
      14022 + df['stoch_oversold'] = df['stoch_k'] < {stoch_level}
      14023 + df['both_oversold'] = df['rsi_oversold'] & df['stoch_oversold']
      14024 + df['turning'] = df['close'] > df['close'].shift(1)
      14025 + df['entry_signal'] = df['both_oversold'] & df['turning']""",
      14026 +         params={"rsi_level": [30, 35], "stoch_level": [20, 25]},
      14027 +         direction="long",
      14028 +         lookback=25,
      14029 +         indicators=["RSI", "STOCH"],
      14030 +         combinable_with=["volume", "confirmation"],
      14031 +         strategy_type="OEX",
      14032 +     ),
      14033 +     # Multi-Osc Oversold
      14034 +     PatternBlock(
      14035 +         id="MULTI_OSC_OVERSOLD",
      14036 +         name="Multi-Oscillator Oversold",
      14037 +         category="oscillator_extreme",
      14038 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      14039 + df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=14)
      14040 + df['willr'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod=14)
      14041 + df['rsi_os'] = df['rsi'] < 35
      14042 + df['cci_os'] = df['cci'] < -100
      14043 + df['willr_os'] = df['willr'] < -80
      14044 + df['multi_os'] = df['rsi_os'] & df['cci_os'] & df['willr_os']
      14045 + df['entry_signal'] = df['multi_os']""",
      14046 +         params={},
      14047 +         direction="long",
      14048 +         lookback=25,
      14049 +         indicators=["RSI", "CCI", "WILLR"],
      14050 +         combinable_with=["volume", "confirmation"],
      14051 +         strategy_type="OEX",
      14052 +     ),
      14053 +     # Oscillator Unanimity
      14054 +     PatternBlock(
      14055 +         id="OSC_UNANIMITY",
      14056 +         name="Oscillator Unanimity",
      14057 +         category="oscillator_extreme",
      14058 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      14059 + df['stoch_k'], _ = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
      14060 + df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
      14061 + df['rsi_turn'] = (df['rsi'] > df['rsi'].shift(1)) & (df['rsi'].shift(1) < 40)
      14062 + df['stoch_turn'] = (df['stoch_k'] > df['stoch_k'].shift(1)) & (df['stoch_k'].shift(1) < 30)
      14063 + df['mfi_turn'] = (df['mfi'] > df['mfi'].shift(1)) & (df['mfi'].shift(1) < 30)
      14064 + df['unanimity'] = df['rsi_turn'] & df['stoch_turn'] & df['mfi_turn']
      14065 + df['entry_signal'] = df['unanimity']""",
      14066 +         params={},
      14067 +         direction="long",
      14068 +         lookback=25,
      14069 +         indicators=["RSI", "STOCH", "MFI"],
      14070 +         combinable_with=["momentum", "confirmation"],
      14071 +         strategy_type="OEX",
      14072 +     ),
      14073 + ]
      14074 +
      14075 +
      14076 + # =============================================================================
      14077 + # VOLUME MOMENTUM BLOCKS
      14078 + # =============================================================================
      14079 +
      14080 + VOLUME_MOMENTUM_BLOCKS = [
      14081 +     # Volume ROC
      14082 +     PatternBlock(
      14083 +         id="VOL_ROC",
      14084 +         name="Volume ROC",
      14085 +         category="volume_momentum",
      14086 +         formula_template="""df['vol_roc'] = (df['volume'] - df['volume'].shift({period})) / df['volume'].shift({period}) * 100
      14087 + df['vol_surge'] = df['vol_roc'] > {threshold}
      14088 + df['price_up'] = df['close'] > df['close'].shift(1)
      14089 + df['entry_signal'] = df['vol_surge'] & df['price_up']""",
      14090 +         params={"period": [5, 10], "threshold": [50, 100]},
      14091 +         direction="long",
      14092 +         lookback=20,
      14093 +         indicators=[],
      14094 +         combinable_with=["momentum", "threshold"],
      14095 +         strategy_type="VMM",
      14096 +     ),
      14097 +     # Volume Acceleration
      14098 +     PatternBlock(
      14099 +         id="VOL_ACCEL",
      14100 +         name="Volume Acceleration",
      14101 +         category="volume_momentum",
      14102 +         formula_template="""df['vol_ma'] = df['volume'].rolling({period}).mean()
      14103 + df['vol_ratio'] = df['volume'] / df['vol_ma']
      14104 + df['vol_accel'] = df['vol_ratio'] - df['vol_ratio'].shift(3)
      14105 + df['accelerating'] = df['vol_accel'] > 0
      14106 + df['high_vol'] = df['vol_ratio'] > 1.5
      14107 + df['bullish'] = df['close'] > df['open']
      14108 + df['entry_signal'] = df['accelerating'] & df['high_vol'] & df['bullish']""",
      14109 +         params={"period": [20]},
      14110 +         direction="long",
      14111 +         lookback=30,
      14112 +         indicators=[],
      14113 +         combinable_with=["momentum", "confirmation"],
      14114 +         strategy_type="VMM",
      14115 +     ),
      14116 +     # Volume Momentum Divergence
      14117 +     PatternBlock(
      14118 +         id="VOL_MOM_DIV",
      14119 +         name="Volume Momentum Divergence",
      14120 +         category="volume_momentum",
      14121 +         formula_template="""df['price_lower'] = df['close'] < df['close'].shift(10)
      14122 + df['vol_higher'] = df['volume'] > df['volume'].shift(10)
      14123 + df['obv'] = ta.OBV(df['close'], df['volume'])
      14124 + df['obv_higher'] = df['obv'] > df['obv'].shift(10)
      14125 + df['vol_div'] = df['price_lower'] & df['vol_higher'] & df['obv_higher']
      14126 + df['entry_signal'] = df['vol_div']""",
      14127 +         params={},
      14128 +         direction="long",
      14129 +         lookback=20,
      14130 +         indicators=["OBV"],
      14131 +         combinable_with=["momentum", "threshold"],
      14132 +         strategy_type="VMM",
      14133 +     ),
      14134 + ]
      14135 +
      14136 +
      14137 + # =============================================================================
      14138 + # CANDLE MOMENTUM BLOCKS
      14139 + # =============================================================================
      14140 +
      14141 + CANDLE_MOMENTUM_BLOCKS = [
      14142 +     # Body Momentum
      14143 +     PatternBlock(
      14144 +         id="BODY_MOMENTUM",
      14145 +         name="Body Momentum",
      14146 +         category="candle_momentum",
      14147 +         formula_template="""df['body'] = abs(df['close'] - df['open'])
      14148 + df['body_ma'] = df['body'].rolling({period}).mean()
      14149 + df['body_ratio'] = df['body'] / df['body_ma']
      14150 + df['strong_body'] = df['body_ratio'] > {threshold}
      14151 + df['bullish'] = df['close'] > df['open']
      14152 + df['entry_signal'] = df['strong_body'] & df['bullish']""",
      14153 +         params={"period": [10], "threshold": [1.5, 2.0]},
      14154 +         direction="long",
      14155 +         lookback=20,
      14156 +         indicators=[],
      14157 +         combinable_with=["volume", "momentum"],
      14158 +         strategy_type="CDM",
      14159 +     ),
      14160 +     # Candle Acceleration
      14161 +     PatternBlock(
      14162 +         id="CANDLE_ACCEL",
      14163 +         name="Candle Acceleration",
      14164 +         category="candle_momentum",
      14165 +         formula_template="""df['body'] = df['close'] - df['open']
      14166 + df['body_1'] = df['body'].shift(1)
      14167 + df['body_2'] = df['body'].shift(2)
      14168 + df['accelerating'] = (df['body'] > df['body_1']) & (df['body_1'] > df['body_2'])
      14169 + df['all_bullish'] = (df['body'] > 0) & (df['body_1'] > 0) & (df['body_2'] > 0)
      14170 + df['entry_signal'] = df['accelerating'] & df['all_bullish']""",
      14171 +         params={},
      14172 +         direction="long",
      14173 +         lookback=10,
      14174 +         indicators=[],
      14175 +         combinable_with=["volume", "confirmation"],
      14176 +         strategy_type="CDM",
      14177 +     ),
      14178 +     # Consecutive Body Growth
      14179 +     PatternBlock(
      14180 +         id="CONSEC_BODY_GROWTH",
      14181 +         name="Consecutive Body Growth",
      14182 +         category="candle_momentum",
      14183 +         formula_template="""df['body'] = abs(df['close'] - df['open'])
      14184 + df['growing'] = df['body'] > df['body'].shift(1) * {mult}
      14185 + df['bullish'] = df['close'] > df['open']
      14186 + df['consec'] = df['growing'] & df['bullish']
      14187 + df['consec_count'] = df['consec'].rolling({count}).sum()
      14188 + df['entry_signal'] = df['consec_count'] >= {count}""",
      14189 +         params={"mult": [1.1, 1.2], "count": [3]},
      14190 +         direction="long",
      14191 +         lookback=15,
      14192 +         indicators=[],
      14193 +         combinable_with=["volume", "momentum"],
      14194 +         strategy_type="CDM",
      14195 +     ),
      14196 + ]
      14197 +
      14198 +
      14199 + # =============================================================================
      14200 + # SUPPORT BOUNCE BLOCKS
      14201 + # =============================================================================
      14202 +
      14203 + SUPPORT_BOUNCE_BLOCKS = [
      14204 +     # Dynamic Support Test
      14205 +     PatternBlock(
      14206 +         id="DYN_SUPPORT_TEST",
      14207 +         name="Dynamic Support Test",
      14208 +         category="support_bounce",
      14209 +         formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
      14210 + df['at_ema'] = df['low'] <= df['ema'] * 1.01
      14211 + df['above_ema'] = df['close'] > df['ema']
      14212 + df['bounce'] = df['at_ema'] & df['above_ema']
      14213 + df['uptrend'] = df['ema'] > df['ema'].shift(5)
      14214 + df['entry_signal'] = df['bounce'] & df['uptrend']""",
      14215 +         params={"period": [20, 50]},
      14216 +         direction="long",
      14217 +         lookback=60,
      14218 +         indicators=["EMA"],
      14219 +         combinable_with=["volume", "momentum"],
      14220 +         strategy_type="SBN",
      14221 +     ),
      14222 +     # Pivot Bounce
      14223 +     PatternBlock(
      14224 +         id="PIVOT_BOUNCE",
      14225 +         name="Pivot Bounce",
      14226 +         category="support_bounce",
      14227 +         formula_template="""df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
      14228 + df['s1'] = 2 * df['pivot'] - df['high'].shift(1)
      14229 + df['at_support'] = df['low'] <= df['s1'] * 1.005
      14230 + df['bounce'] = df['close'] > df['open']
      14231 + df['above_s1'] = df['close'] > df['s1']
      14232 + df['entry_signal'] = df['at_support'] & df['bounce'] & df['above_s1']""",
      14233 +         params={},
      14234 +         direction="long",
      14235 +         lookback=10,
      14236 +         indicators=[],
      14237 +         combinable_with=["volume", "confirmation"],
      14238 +         strategy_type="SBN",
      14239 +     ),
      14240 +     # MA Support Touch
      14241 +     PatternBlock(
      14242 +         id="MA_SUPPORT_TOUCH",
      14243 +         name="MA Support Touch",
      14244 +         category="support_bounce",
      14245 +         formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
      14246 + df['touches'] = (df['low'] <= df['sma'] * 1.005) & (df['close'] > df['sma'])
      14247 + df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
      14248 + df['entry_signal'] = df['touches'] & df['vol_confirm']""",
      14249 +         params={"period": [20, 50]},
      14250 +         direction="long",
      14251 +         lookback=60,
      14252 +         indicators=["SMA"],
      14253 +         combinable_with=["momentum", "threshold"],
      14254 +         strategy_type="SBN",
      14255 +     ),
      14256 + ]
      14257 +
      14258 +
      14259 + # =============================================================================
      14260 + # BREAKOUT STRENGTH BLOCKS
      14261 + # =============================================================================
      14262 +
      14263 + BREAKOUT_STRENGTH_BLOCKS = [
      14264 +     # Volume-Confirmed Break
      14265 +     PatternBlock(
      14266 +         id="VOL_CONFIRM_BREAK",
      14267 +         name="Volume-Confirmed Break",
      14268 +         category="breakout_strength",
      14269 +         formula_template="""df['high_20'] = df['high'].rolling(20).max()
      14270 + df['break_high'] = df['close'] > df['high_20'].shift(1)
      14271 + df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
      14272 + df['entry_signal'] = df['break_high'] & df['vol_surge']""",
      14273 +         params={"mult": [1.5, 2.0]},
      14274 +         direction="long",
      14275 +         lookback=30,
      14276 +         indicators=[],
      14277 +         combinable_with=["momentum", "confirmation"],
      14278 +         strategy_type="BKS",
      14279 +     ),
      14280 +     # ATR Break Magnitude
      14281 +     PatternBlock(
      14282 +         id="ATR_BREAK_MAG",
      14283 +         name="ATR Break Magnitude",
      14284 +         category="breakout_strength",
      14285 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
      14286 + df['prev_high'] = df['high'].shift(1).rolling(10).max()
      14287 + df['break_size'] = df['close'] - df['prev_high']
      14288 + df['strong_break'] = df['break_size'] > df['atr'] * {mult}
      14289 + df['entry_signal'] = df['strong_break']""",
      14290 +         params={"mult": [1.0, 1.5]},
      14291 +         direction="long",
      14292 +         lookback=25,
      14293 +         indicators=["ATR"],
      14294 +         combinable_with=["volume", "confirmation"],
      14295 +         strategy_type="BKS",
      14296 +     ),
      14297 +     # Multi-Bar Break
      14298 +     PatternBlock(
      14299 +         id="MULTI_BAR_BREAK",
      14300 +         name="Multi-Bar Break",
      14301 +         category="breakout_strength",
      14302 +         formula_template="""df['high_10'] = df['high'].rolling(10).max()
      14303 + df['break'] = df['close'] > df['high_10'].shift(1)
      14304 + df['consec_break'] = df['break'].rolling({bars}).sum() >= {bars}
      14305 + df['vol_up'] = df['volume'] > df['volume'].shift(1)
      14306 + df['entry_signal'] = df['consec_break'] & df['vol_up']""",
      14307 +         params={"bars": [2, 3]},
      14308 +         direction="long",
      14309 +         lookback=20,
      14310 +         indicators=[],
      14311 +         combinable_with=["momentum", "threshold"],
      14312 +         strategy_type="BKS",
      14313 +     ),
      14314 + ]
      14315 +
      14316 +
      14317 + # =============================================================================
      14318   # ALL BLOCKS COMBINED
      14319   # =============================================================================
      14320

● Search(pattern: "ADAPTIVE_RSI_BLOCKS$", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 30 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      14513       + MOMENTUM_PERCENTILE_BLOCKS
      14514       + TREND_SCORE_BLOCKS
      14515       + ADAPTIVE_RSI_BLOCKS
      14516 +     + RATE_OF_CHANGE_EXT_BLOCKS
      14517 +     + VOLATILITY_BREAKOUT_BLOCKS
      14518 +     + PRICE_DENSITY_BLOCKS
      14519 +     + MOMENTUM_DIVERGENCE_EXT_BLOCKS
      14520 +     + TREND_CONFIRMATION_BLOCKS
      14521 +     + OSCILLATOR_EXTREME_BLOCKS
      14522 +     + VOLUME_MOMENTUM_BLOCKS
      14523 +     + CANDLE_MOMENTUM_BLOCKS
      14524 +     + SUPPORT_BOUNCE_BLOCKS
      14525 +     + BREAKOUT_STRENGTH_BLOCKS
      14526   )
      14527
      14528   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python3 << 'EOF'
      import sys…)
  ⎿  Total blocks: 718
     Categories: 203
     … +35 lines (ctrl+o to expand)

● Round 20 completato!

  Risultati:
  - Blocchi totali: 718 (+30 nuovi)
  - Categorie: 203
  - Tipi strategia: 192
  - Validazione: 200/200 strategie valide
  - Lookahead: Nessun pattern rilevato
  - Strategie stimate: ~140,104

  Nuovi blocchi aggiunti (Round 20):
  1. RATE_OF_CHANGE_EXT_BLOCKS (RCX): ROC smoothed/percentile/acceleration
  2. VOLATILITY_BREAKOUT_BLOCKS (VBK): ATR expansion/squeeze break/range breakout
  3. PRICE_DENSITY_BLOCKS (PDN): Clustering/consolidation/distribution width
  4. MOMENTUM_DIVERGENCE_EXT_BLOCKS (MDV): Multi-indicator/hidden/triple divergence
  5. TREND_CONFIRMATION_BLOCKS (TCF): Multi-MA alignment/ADX+DI/unanimity
  6. OSCILLATOR_EXTREME_BLOCKS (OEX): RSI+Stoch/multi-osc oversold/unanimity
  7. VOLUME_MOMENTUM_BLOCKS (VMM): Volume ROC/acceleration/momentum divergence
  8. CANDLE_MOMENTUM_BLOCKS (CDM): Body momentum/acceleration/consecutive growth
  9. SUPPORT_BOUNCE_BLOCKS (SBN): Dynamic support/pivot bounce/MA touch
  10. BREAKOUT_STRENGTH_BLOCKS (BKS): Volume-confirmed/ATR magnitude/multi-bar

  Progressione sessione:
  ┌─────────────┬─────────┬───────────────────┐
  │    Round    │ Blocchi │ Strategie stimate │
  ├─────────────┼─────────┼───────────────────┤
  │ 11 (inizio) │ 447     │ ~100,392          │
  ├─────────────┼─────────┼───────────────────┤
  │ ...         │ ...     │ ...               │
  ├─────────────┼─────────┼───────────────────┤
  │ 19          │ 688     │ ~135,824          │
  ├─────────────┼─────────┼───────────────────┤
  │ 20          │ 718     │ ~140,104          │
  └─────────────┴─────────┴───────────────────┘
  Hai testato che tutto funzioni? Altre possibili migliorie? (stessi requisiti)

✻ Churned for 2m 37s

❯ hai testato che tutto funzioni?
  altre possibili migliorie? con gli stessi requisiti, cioè no modifiche al codice esistente, piena compatibilità, no diminuzione strategie
  dimmi solo

● Test Round 20: PASSATO
  - 200/200 strategie valide
  - 0 errori lookahead
  - 718 blocchi funzionanti

  ---
  Proposta Round 21 - 10 nuove categorie (30 blocchi):

  1. RESISTANCE_REJECTION_BLOCKS (RRJ): Dynamic resistance test, pivot rejection, MA resistance touch
  2. PULLBACK_ENTRY_BLOCKS (PBE): Trend pullback, EMA pullback, Fibonacci retracement zone
  3. MOMENTUM_EXHAUSTION_BLOCKS (MEX2): RSI exhaustion, momentum deceleration, climax reversal
  4. VOLUME_PROFILE_EXT_BLOCKS (VPX): High volume node, low volume gap, volume POC
  5. TREND_CHANGE_BLOCKS (TCH): MA crossover confirm, ADX trend shift, momentum flip
  6. RANGE_BOUND_BLOCKS (RGB): Range detection, mean reversion setup, channel midline
  7. MULTI_TIMEFRAME_PROXY_BLOCKS (MTF): Higher MA alignment, multi-period momentum, trend stack
  8. PRICE_STRUCTURE_BLOCKS (PST): Higher high confirm, lower low break, structure shift
  9. VOLATILITY_REGIME_EXT_BLOCKS (VRE): Vol expansion phase, contraction alert, regime change
  10. SMART_MONEY_BLOCKS (SMB): Accumulation pattern, distribution detect, institutional volume

  Risultato atteso:
  - Blocchi: 718 → 748 (+30)
  - Strategie: ~140,104 → ~144,500+

  Vuoi procedere?

❯ si

● Search(pattern: "^BREAKOUT_STRENGTH_BLOCKS = \[", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 50 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 624 lines
      14315
      14316
      14317   # =============================================================================
      14318 + # RESISTANCE REJECTION BLOCKS
      14319 + # =============================================================================
      14320 +
      14321 + RESISTANCE_REJECTION_BLOCKS = [
      14322 +     # Dynamic Resistance Test
      14323 +     PatternBlock(
      14324 +         id="DYN_RESISTANCE_TEST",
      14325 +         name="Dynamic Resistance Test",
      14326 +         category="resistance_rejection",
      14327 +         formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
      14328 + df['at_ema'] = df['high'] >= df['ema'] * 0.99
      14329 + df['below_ema'] = df['close'] < df['ema']
      14330 + df['rejection'] = df['at_ema'] & df['below_ema']
      14331 + df['downtrend'] = df['ema'] < df['ema'].shift(5)
      14332 + df['entry_signal'] = df['rejection'] & df['downtrend']""",
      14333 +         params={"period": [20, 50]},
      14334 +         direction="short",
      14335 +         lookback=60,
      14336 +         indicators=["EMA"],
      14337 +         combinable_with=["volume", "momentum"],
      14338 +         strategy_type="RRJ",
      14339 +     ),
      14340 +     # Pivot Rejection
      14341 +     PatternBlock(
      14342 +         id="PIVOT_REJECTION",
      14343 +         name="Pivot Rejection",
      14344 +         category="resistance_rejection",
      14345 +         formula_template="""df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
      14346 + df['r1'] = 2 * df['pivot'] - df['low'].shift(1)
      14347 + df['at_resistance'] = df['high'] >= df['r1'] * 0.995
      14348 + df['rejection'] = df['close'] < df['open']
      14349 + df['below_r1'] = df['close'] < df['r1']
      14350 + df['entry_signal'] = df['at_resistance'] & df['rejection'] & df['below_r1']""",
      14351 +         params={},
      14352 +         direction="short",
      14353 +         lookback=10,
      14354 +         indicators=[],
      14355 +         combinable_with=["volume", "confirmation"],
      14356 +         strategy_type="RRJ",
      14357 +     ),
      14358 +     # MA Resistance Touch
      14359 +     PatternBlock(
      14360 +         id="MA_RESISTANCE_TOUCH",
      14361 +         name="MA Resistance Touch",
      14362 +         category="resistance_rejection",
      14363 +         formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
      14364 + df['touches'] = (df['high'] >= df['sma'] * 0.995) & (df['close'] < df['sma'])
      14365 + df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
      14366 + df['entry_signal'] = df['touches'] & df['vol_confirm']""",
      14367 +         params={"period": [20, 50]},
      14368 +         direction="short",
      14369 +         lookback=60,
      14370 +         indicators=["SMA"],
      14371 +         combinable_with=["momentum", "threshold"],
      14372 +         strategy_type="RRJ",
      14373 +     ),
      14374 + ]
      14375 +
      14376 +
      14377 + # =============================================================================
      14378 + # PULLBACK ENTRY BLOCKS
      14379 + # =============================================================================
      14380 +
      14381 + PULLBACK_ENTRY_BLOCKS = [
      14382 +     # Trend Pullback
      14383 +     PatternBlock(
      14384 +         id="TREND_PULLBACK",
      14385 +         name="Trend Pullback",
      14386 +         category="pullback_entry",
      14387 +         formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod=20)
      14388 + df['ema_slow'] = ta.EMA(df['close'], timeperiod=50)
      14389 + df['uptrend'] = df['ema_fast'] > df['ema_slow']
      14390 + df['pullback'] = df['low'] <= df['ema_fast'] * 1.01
      14391 + df['bounce'] = df['close'] > df['ema_fast']
      14392 + df['entry_signal'] = df['uptrend'] & df['pullback'] & df['bounce']""",
      14393 +         params={},
      14394 +         direction="long",
      14395 +         lookback=60,
      14396 +         indicators=["EMA"],
      14397 +         combinable_with=["volume", "momentum"],
      14398 +         strategy_type="PBE",
      14399 +     ),
      14400 +     # EMA Pullback
      14401 +     PatternBlock(
      14402 +         id="EMA_PULLBACK",
      14403 +         name="EMA Pullback",
      14404 +         category="pullback_entry",
      14405 +         formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
      14406 + df['above_ema'] = df['close'].shift(5) > df['ema'].shift(5)
      14407 + df['touched'] = df['low'] <= df['ema'] * 1.005
      14408 + df['recovered'] = df['close'] > df['ema']
      14409 + df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      14410 + df['not_overbought'] = df['rsi'] < 70
      14411 + df['entry_signal'] = df['above_ema'] & df['touched'] & df['recovered'] & df['not_overbought']""",
      14412 +         params={"period": [20, 50]},
      14413 +         direction="long",
      14414 +         lookback=60,
      14415 +         indicators=["EMA", "RSI"],
      14416 +         combinable_with=["volume", "confirmation"],
      14417 +         strategy_type="PBE",
      14418 +     ),
      14419 +     # Fibonacci Retracement Zone
      14420 +     PatternBlock(
      14421 +         id="FIB_RETRACE_ZONE",
      14422 +         name="Fibonacci Retracement Zone",
      14423 +         category="pullback_entry",
      14424 +         formula_template="""df['high_20'] = df['high'].rolling(20).max()
      14425 + df['low_20'] = df['low'].rolling(20).min()
      14426 + df['range'] = df['high_20'] - df['low_20']
      14427 + df['fib_382'] = df['high_20'] - df['range'] * 0.382
      14428 + df['fib_618'] = df['high_20'] - df['range'] * 0.618
      14429 + df['in_zone'] = (df['low'] <= df['fib_382']) & (df['low'] >= df['fib_618'])
      14430 + df['bounce'] = df['close'] > df['open']
      14431 + df['entry_signal'] = df['in_zone'] & df['bounce']""",
      14432 +         params={},
      14433 +         direction="long",
      14434 +         lookback=30,
      14435 +         indicators=[],
      14436 +         combinable_with=["volume", "momentum"],
      14437 +         strategy_type="PBE",
      14438 +     ),
      14439 + ]
      14440 +
      14441 +
      14442 + # =============================================================================
      14443 + # MOMENTUM EXHAUSTION BLOCKS (MEX2)
      14444 + # =============================================================================
      14445 +
      14446 + MOMENTUM_EXHAUSTION_EXT_BLOCKS = [
      14447 +     # RSI Exhaustion
      14448 +     PatternBlock(
      14449 +         id="RSI_EXHAUSTION",
      14450 +         name="RSI Exhaustion",
      14451 +         category="momentum_exhaustion_ext",
      14452 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      14453 + df['was_extreme'] = df['rsi'].shift(3) > {level}
      14454 + df['falling'] = df['rsi'] < df['rsi'].shift(1)
      14455 + df['still_high'] = df['rsi'] > 50
      14456 + df['exhaustion'] = df['was_extreme'] & df['falling'] & df['still_high']
      14457 + df['entry_signal'] = df['exhaustion']""",
      14458 +         params={"level": [75, 80]},
      14459 +         direction="short",
      14460 +         lookback=25,
      14461 +         indicators=["RSI"],
      14462 +         combinable_with=["volume", "confirmation"],
      14463 +         strategy_type="MEX",
      14464 +     ),
      14465 +     # Momentum Deceleration
      14466 +     PatternBlock(
      14467 +         id="MOM_DECELERATION",
      14468 +         name="Momentum Deceleration",
      14469 +         category="momentum_exhaustion_ext",
      14470 +         formula_template="""df['mom'] = ta.MOM(df['close'], timeperiod=10)
      14471 + df['mom_accel'] = df['mom'] - df['mom'].shift(3)
      14472 + df['decelerating'] = df['mom_accel'] < 0
      14473 + df['still_positive'] = df['mom'] > 0
      14474 + df['high_price'] = df['close'] > df['close'].rolling(20).mean()
      14475 + df['entry_signal'] = df['decelerating'] & df['still_positive'] & df['high_price']""",
      14476 +         params={},
      14477 +         direction="short",
      14478 +         lookback=30,
      14479 +         indicators=["MOM"],
      14480 +         combinable_with=["volume", "threshold"],
      14481 +         strategy_type="MEX",
      14482 +     ),
      14483 +     # Climax Reversal
      14484 +     PatternBlock(
      14485 +         id="CLIMAX_REVERSAL",
      14486 +         name="Climax Reversal",
      14487 +         category="momentum_exhaustion_ext",
      14488 +         formula_template="""df['range'] = df['high'] - df['low']
      14489 + df['avg_range'] = df['range'].rolling(20).mean()
      14490 + df['climax_bar'] = df['range'] > df['avg_range'] * {mult}
      14491 + df['vol_climax'] = df['volume'] > df['volume'].rolling(20).mean() * 2
      14492 + df['reversal'] = df['close'] < df['open']
      14493 + df['entry_signal'] = df['climax_bar'] & df['vol_climax'] & df['reversal']""",
      14494 +         params={"mult": [2.0, 2.5]},
      14495 +         direction="short",
      14496 +         lookback=30,
      14497 +         indicators=[],
      14498 +         combinable_with=["momentum", "confirmation"],
      14499 +         strategy_type="MEX",
      14500 +     ),
      14501 + ]
      14502 +
      14503 +
      14504 + # =============================================================================
      14505 + # VOLUME PROFILE EXTENDED BLOCKS
      14506 + # =============================================================================
      14507 +
      14508 + VOLUME_PROFILE_EXT_BLOCKS = [
      14509 +     # High Volume Node
      14510 +     PatternBlock(
      14511 +         id="HIGH_VOL_NODE",
      14512 +         name="High Volume Node",
      14513 +         category="volume_profile_ext",
      14514 +         formula_template="""df['vol_ma'] = df['volume'].rolling({period}).mean()
      14515 + df['high_vol'] = df['volume'] > df['vol_ma'] * {mult}
      14516 + df['price_level'] = df['close'].rolling(5).mean()
      14517 + df['at_hvn'] = abs(df['close'] - df['price_level']) / df['close'] < 0.01
      14518 + df['bullish'] = df['close'] > df['open']
      14519 + df['entry_signal'] = df['high_vol'].shift(1) & df['at_hvn'] & df['bullish']""",
      14520 +         params={"period": [20], "mult": [1.5, 2.0]},
      14521 +         direction="long",
      14522 +         lookback=30,
      14523 +         indicators=[],
      14524 +         combinable_with=["momentum", "confirmation"],
      14525 +         strategy_type="VPX",
      14526 +     ),
      14527 +     # Low Volume Gap
      14528 +     PatternBlock(
      14529 +         id="LOW_VOL_GAP",
      14530 +         name="Low Volume Gap",
      14531 +         category="volume_profile_ext",
      14532 +         formula_template="""df['vol_ma'] = df['volume'].rolling(20).mean()
      14533 + df['low_vol_zone'] = df['volume'] < df['vol_ma'] * 0.5
      14534 + df['low_vol_days'] = df['low_vol_zone'].rolling(5).sum() >= 3
      14535 + df['break_up'] = df['close'] > df['high'].shift(1).rolling(5).max()
      14536 + df['vol_increase'] = df['volume'] > df['vol_ma']
      14537 + df['entry_signal'] = df['low_vol_days'].shift(1) & df['break_up'] & df['vol_increase']""",
      14538 +         params={},
      14539 +         direction="long",
      14540 +         lookback=35,
      14541 +         indicators=[],
      14542 +         combinable_with=["momentum", "threshold"],
      14543 +         strategy_type="VPX",
      14544 +     ),
      14545 +     # Volume POC
      14546 +     PatternBlock(
      14547 +         id="VOL_POC",
      14548 +         name="Volume POC",
      14549 +         category="volume_profile_ext",
      14550 +         formula_template="""df['vwap'] = (df['close'] * df['volume']).rolling({period}).sum() /
            +df['volume'].rolling({period}).sum()
      14551 + df['at_poc'] = abs(df['close'] - df['vwap']) / df['close'] < 0.005
      14552 + df['bounce'] = df['close'] > df['open']
      14553 + df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
      14554 + df['entry_signal'] = df['at_poc'] & df['bounce'] & df['vol_confirm']""",
      14555 +         params={"period": [20]},
      14556 +         direction="long",
      14557 +         lookback=30,
      14558 +         indicators=[],
      14559 +         combinable_with=["volume", "confirmation"],
      14560 +         strategy_type="VPX",
      14561 +     ),
      14562 + ]
      14563 +
      14564 +
      14565 + # =============================================================================
      14566 + # TREND CHANGE BLOCKS
      14567 + # =============================================================================
      14568 +
      14569 + TREND_CHANGE_BLOCKS = [
      14570 +     # MA Crossover Confirm
      14571 +     PatternBlock(
      14572 +         id="MA_CROSS_CONFIRM",
      14573 +         name="MA Crossover Confirm",
      14574 +         category="trend_change",
      14575 +         formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
      14576 + df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
      14577 + df['cross_up'] = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
      14578 + df['price_confirm'] = df['close'] > df['ema_fast']
      14579 + df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
      14580 + df['entry_signal'] = df['cross_up'] & df['price_confirm'] & df['vol_confirm']""",
      14581 +         params={"fast": [10, 20], "slow": [50]},
      14582 +         direction="long",
      14583 +         lookback=60,
      14584 +         indicators=["EMA"],
      14585 +         combinable_with=["momentum", "confirmation"],
      14586 +         strategy_type="TCH",
      14587 +     ),
      14588 +     # ADX Trend Shift
      14589 +     PatternBlock(
      14590 +         id="ADX_TREND_SHIFT",
      14591 +         name="ADX Trend Shift",
      14592 +         category="trend_change",
      14593 +         formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
      14594 + df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
      14595 + df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
      14596 + df['di_cross'] = (df['plus_di'] > df['minus_di']) & (df['plus_di'].shift(1) <= df['minus_di'].shift(1))
      14597 + df['adx_rising'] = df['adx'] > df['adx'].shift(3)
      14598 + df['entry_signal'] = df['di_cross'] & df['adx_rising']""",
      14599 +         params={},
      14600 +         direction="long",
      14601 +         lookback=25,
      14602 +         indicators=["ADX", "PLUS_DI", "MINUS_DI"],
      14603 +         combinable_with=["volume", "threshold"],
      14604 +         strategy_type="TCH",
      14605 +     ),
      14606 +     # Momentum Flip
      14607 +     PatternBlock(
      14608 +         id="MOMENTUM_FLIP",
      14609 +         name="Momentum Flip",
      14610 +         category="trend_change",
      14611 +         formula_template="""df['macd'], df['macd_signal'], df['macd_hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26,
            +signalperiod=9)
      14612 + df['hist_flip'] = (df['macd_hist'] > 0) & (df['macd_hist'].shift(1) <= 0)
      14613 + df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      14614 + df['rsi_confirm'] = df['rsi'] > 50
      14615 + df['entry_signal'] = df['hist_flip'] & df['rsi_confirm']""",
      14616 +         params={},
      14617 +         direction="long",
      14618 +         lookback=35,
      14619 +         indicators=["MACD", "RSI"],
      14620 +         combinable_with=["volume", "confirmation"],
      14621 +         strategy_type="TCH",
      14622 +     ),
      14623 + ]
      14624 +
      14625 +
      14626 + # =============================================================================
      14627 + # RANGE BOUND BLOCKS
      14628 + # =============================================================================
      14629 +
      14630 + RANGE_BOUND_BLOCKS = [
      14631 +     # Range Detection
      14632 +     PatternBlock(
      14633 +         id="RANGE_DETECTION",
      14634 +         name="Range Detection",
      14635 +         category="range_bound",
      14636 +         formula_template="""df['high_20'] = df['high'].rolling(20).max()
      14637 + df['low_20'] = df['low'].rolling(20).min()
      14638 + df['range_pct'] = (df['high_20'] - df['low_20']) / df['close'] * 100
      14639 + df['tight_range'] = df['range_pct'] < {threshold}
      14640 + df['at_bottom'] = df['close'] < df['low_20'] + (df['high_20'] - df['low_20']) * 0.3
      14641 + df['bounce'] = df['close'] > df['close'].shift(1)
      14642 + df['entry_signal'] = df['tight_range'] & df['at_bottom'] & df['bounce']""",
      14643 +         params={"threshold": [5, 8]},
      14644 +         direction="long",
      14645 +         lookback=30,
      14646 +         indicators=[],
      14647 +         combinable_with=["volume", "momentum"],
      14648 +         strategy_type="RGB",
      14649 +     ),
      14650 +     # Mean Reversion Setup
      14651 +     PatternBlock(
      14652 +         id="MEAN_REVERSION_SETUP",
      14653 +         name="Mean Reversion Setup",
      14654 +         category="range_bound",
      14655 +         formula_template="""df['sma'] = ta.SMA(df['close'], timeperiod={period})
      14656 + df['std'] = df['close'].rolling({period}).std()
      14657 + df['lower_band'] = df['sma'] - df['std'] * {mult}
      14658 + df['at_lower'] = df['close'] <= df['lower_band']
      14659 + df['reversal'] = df['close'] > df['open']
      14660 + df['entry_signal'] = df['at_lower'] & df['reversal']""",
      14661 +         params={"period": [20], "mult": [1.5, 2.0]},
      14662 +         direction="long",
      14663 +         lookback=30,
      14664 +         indicators=["SMA"],
      14665 +         combinable_with=["volume", "threshold"],
      14666 +         strategy_type="RGB",
      14667 +     ),
      14668 +     # Channel Midline
      14669 +     PatternBlock(
      14670 +         id="CHANNEL_MIDLINE",
      14671 +         name="Channel Midline",
      14672 +         category="range_bound",
      14673 +         formula_template="""df['high_ch'] = df['high'].rolling({period}).max()
      14674 + df['low_ch'] = df['low'].rolling({period}).min()
      14675 + df['midline'] = (df['high_ch'] + df['low_ch']) / 2
      14676 + df['cross_up'] = (df['close'] > df['midline']) & (df['close'].shift(1) <= df['midline'].shift(1))
      14677 + df['vol_up'] = df['volume'] > df['volume'].rolling(10).mean()
      14678 + df['entry_signal'] = df['cross_up'] & df['vol_up']""",
      14679 +         params={"period": [20]},
      14680 +         direction="long",
      14681 +         lookback=30,
      14682 +         indicators=[],
      14683 +         combinable_with=["momentum", "confirmation"],
      14684 +         strategy_type="RGB",
      14685 +     ),
      14686 + ]
      14687 +
      14688 +
      14689 + # =============================================================================
      14690 + # MULTI TIMEFRAME PROXY BLOCKS
      14691 + # =============================================================================
      14692 +
      14693 + MULTI_TIMEFRAME_PROXY_BLOCKS = [
      14694 +     # Higher MA Alignment
      14695 +     PatternBlock(
      14696 +         id="HIGHER_MA_ALIGN",
      14697 +         name="Higher MA Alignment",
      14698 +         category="multi_timeframe_proxy",
      14699 +         formula_template="""df['ema20'] = ta.EMA(df['close'], timeperiod=20)
      14700 + df['ema50'] = ta.EMA(df['close'], timeperiod=50)
      14701 + df['ema100'] = ta.EMA(df['close'], timeperiod=100)
      14702 + df['ema200'] = ta.EMA(df['close'], timeperiod=200)
      14703 + df['aligned'] = (df['ema20'] > df['ema50']) & (df['ema50'] > df['ema100']) & (df['ema100'] > df['ema200'])
      14704 + df['price_above'] = df['close'] > df['ema20']
      14705 + df['entry_signal'] = df['aligned'] & df['price_above']""",
      14706 +         params={},
      14707 +         direction="long",
      14708 +         lookback=210,
      14709 +         indicators=["EMA"],
      14710 +         combinable_with=["momentum", "volume"],
      14711 +         strategy_type="MTF",
      14712 +     ),
      14713 +     # Multi-Period Momentum
      14714 +     PatternBlock(
      14715 +         id="MULTI_PERIOD_MOM",
      14716 +         name="Multi-Period Momentum",
      14717 +         category="multi_timeframe_proxy",
      14718 +         formula_template="""df['roc_5'] = ta.ROC(df['close'], timeperiod=5)
      14719 + df['roc_10'] = ta.ROC(df['close'], timeperiod=10)
      14720 + df['roc_20'] = ta.ROC(df['close'], timeperiod=20)
      14721 + df['all_positive'] = (df['roc_5'] > 0) & (df['roc_10'] > 0) & (df['roc_20'] > 0)
      14722 + df['accelerating'] = df['roc_5'] > df['roc_10']
      14723 + df['entry_signal'] = df['all_positive'] & df['accelerating']""",
      14724 +         params={},
      14725 +         direction="long",
      14726 +         lookback=30,
      14727 +         indicators=["ROC"],
      14728 +         combinable_with=["volume", "threshold"],
      14729 +         strategy_type="MTF",
      14730 +     ),
      14731 +     # Trend Stack
      14732 +     PatternBlock(
      14733 +         id="TREND_STACK",
      14734 +         name="Trend Stack",
      14735 +         category="multi_timeframe_proxy",
      14736 +         formula_template="""df['above_sma20'] = df['close'] > ta.SMA(df['close'], timeperiod=20)
      14737 + df['above_sma50'] = df['close'] > ta.SMA(df['close'], timeperiod=50)
      14738 + df['above_sma100'] = df['close'] > ta.SMA(df['close'], timeperiod=100)
      14739 + df['stack_score'] = df['above_sma20'].astype(int) + df['above_sma50'].astype(int) + df['above_sma100'].astype(int)
      14740 + df['full_stack'] = df['stack_score'] == 3
      14741 + df['was_partial'] = df['stack_score'].shift(1) == 2
      14742 + df['entry_signal'] = df['full_stack'] & df['was_partial']""",
      14743 +         params={},
      14744 +         direction="long",
      14745 +         lookback=110,
      14746 +         indicators=["SMA"],
      14747 +         combinable_with=["momentum", "confirmation"],
      14748 +         strategy_type="MTF",
      14749 +     ),
      14750 + ]
      14751 +
      14752 +
      14753 + # =============================================================================
      14754 + # PRICE STRUCTURE BLOCKS
      14755 + # =============================================================================
      14756 +
      14757 + PRICE_STRUCTURE_BLOCKS = [
      14758 +     # Higher High Confirm
      14759 +     PatternBlock(
      14760 +         id="HIGHER_HIGH_CONFIRM",
      14761 +         name="Higher High Confirm",
      14762 +         category="price_structure",
      14763 +         formula_template="""df['high_5'] = df['high'].rolling(5).max()
      14764 + df['prev_high'] = df['high_5'].shift(5)
      14765 + df['higher_high'] = df['high_5'] > df['prev_high']
      14766 + df['close_strong'] = df['close'] > df['close'].shift(5)
      14767 + df['vol_confirm'] = df['volume'] > df['volume'].rolling(10).mean()
      14768 + df['entry_signal'] = df['higher_high'] & df['close_strong'] & df['vol_confirm']""",
      14769 +         params={},
      14770 +         direction="long",
      14771 +         lookback=20,
      14772 +         indicators=[],
      14773 +         combinable_with=["momentum", "threshold"],
      14774 +         strategy_type="PST",
      14775 +     ),
      14776 +     # Lower Low Break
      14777 +     PatternBlock(
      14778 +         id="LOWER_LOW_BREAK",
      14779 +         name="Lower Low Break",
      14780 +         category="price_structure",
      14781 +         formula_template="""df['low_5'] = df['low'].rolling(5).min()
      14782 + df['prev_low'] = df['low_5'].shift(5)
      14783 + df['lower_low'] = df['low_5'] < df['prev_low']
      14784 + df['reversal'] = df['close'] > df['open']
      14785 + df['reclaim'] = df['close'] > df['prev_low']
      14786 + df['entry_signal'] = df['lower_low'].shift(1) & df['reversal'] & df['reclaim']""",
      14787 +         params={},
      14788 +         direction="long",
      14789 +         lookback=20,
      14790 +         indicators=[],
      14791 +         combinable_with=["volume", "confirmation"],
      14792 +         strategy_type="PST",
      14793 +     ),
      14794 +     # Structure Shift
      14795 +     PatternBlock(
      14796 +         id="STRUCTURE_SHIFT",
      14797 +         name="Structure Shift",
      14798 +         category="price_structure",
      14799 +         formula_template="""df['swing_high'] = df['high'].rolling({period}).max()
      14800 + df['swing_low'] = df['low'].rolling({period}).min()
      14801 + df['break_high'] = df['close'] > df['swing_high'].shift(1)
      14802 + df['was_downtrend'] = df['close'].shift(5) < df['close'].shift(10)
      14803 + df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
      14804 + df['entry_signal'] = df['break_high'] & df['was_downtrend'] & df['vol_surge']""",
      14805 +         params={"period": [10]},
      14806 +         direction="long",
      14807 +         lookback=25,
      14808 +         indicators=[],
      14809 +         combinable_with=["momentum", "confirmation"],
      14810 +         strategy_type="PST",
      14811 +     ),
      14812 + ]
      14813 +
      14814 +
      14815 + # =============================================================================
      14816 + # VOLATILITY REGIME EXTENDED BLOCKS
      14817 + # =============================================================================
      14818 +
      14819 + VOLATILITY_REGIME_EXT_BLOCKS = [
      14820 +     # Vol Expansion Phase
      14821 +     PatternBlock(
      14822 +         id="VOL_EXPANSION_PHASE",
      14823 +         name="Vol Expansion Phase",
      14824 +         category="volatility_regime_ext",
      14825 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
      14826 + df['atr_ma'] = df['atr'].rolling(20).mean()
      14827 + df['expansion'] = df['atr'] > df['atr_ma'] * {mult}
      14828 + df['trend_up'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
      14829 + df['entry_signal'] = df['expansion'] & df['trend_up']""",
      14830 +         params={"mult": [1.3, 1.5]},
      14831 +         direction="long",
      14832 +         lookback=35,
      14833 +         indicators=["ATR", "EMA"],
      14834 +         combinable_with=["momentum", "volume"],
      14835 +         strategy_type="VRE",
      14836 +     ),
      14837 +     # Contraction Alert
      14838 +     PatternBlock(
      14839 +         id="CONTRACTION_ALERT",
      14840 +         name="Contraction Alert",
      14841 +         category="volatility_regime_ext",
      14842 +         formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2,
            +nbdevdn=2)
      14843 + df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
      14844 + df['width_pct'] = df['bb_width'].rolling(50).apply(lambda x: (x.iloc[-1] < x).sum() / len(x) * 100, raw=False)
      14845 + df['extreme_contraction'] = df['width_pct'] < {threshold}
      14846 + df['entry_signal'] = df['extreme_contraction']""",
      14847 +         params={"threshold": [10, 20]},
      14848 +         direction="bidi",
      14849 +         lookback=60,
      14850 +         indicators=["BBANDS"],
      14851 +         combinable_with=["volume", "momentum"],
      14852 +         strategy_type="VRE",
      14853 +     ),
      14854 +     # Regime Change
      14855 +     PatternBlock(
      14856 +         id="REGIME_CHANGE",
      14857 +         name="Regime Change",
      14858 +         category="volatility_regime_ext",
      14859 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
      14860 + df['atr_fast'] = df['atr'].rolling(5).mean()
      14861 + df['atr_slow'] = df['atr'].rolling(20).mean()
      14862 + df['regime_shift'] = (df['atr_fast'] > df['atr_slow'] * {mult}) & (df['atr_fast'].shift(3) <= df['atr_slow'].shift(3))
      14863 + df['direction'] = df['close'] > df['close'].shift(3)
      14864 + df['entry_signal'] = df['regime_shift'] & df['direction']""",
      14865 +         params={"mult": [1.2, 1.5]},
      14866 +         direction="long",
      14867 +         lookback=35,
      14868 +         indicators=["ATR"],
      14869 +         combinable_with=["momentum", "confirmation"],
      14870 +         strategy_type="VRE",
      14871 +     ),
      14872 + ]
      14873 +
      14874 +
      14875 + # =============================================================================
      14876 + # SMART MONEY BLOCKS
      14877 + # =============================================================================
      14878 +
      14879 + SMART_MONEY_BLOCKS = [
      14880 +     # Accumulation Pattern
      14881 +     PatternBlock(
      14882 +         id="ACCUMULATION_PATTERN",
      14883 +         name="Accumulation Pattern",
      14884 +         category="smart_money",
      14885 +         formula_template="""df['range'] = df['high'] - df['low']
      14886 + df['narrow_range'] = df['range'] < df['range'].rolling(20).mean() * 0.7
      14887 + df['high_volume'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
      14888 + df['close_high'] = df['close'] > (df['high'] + df['low']) / 2
      14889 + df['accumulation'] = df['narrow_range'] & df['high_volume'] & df['close_high']
      14890 + df['accum_count'] = df['accumulation'].rolling(10).sum()
      14891 + df['entry_signal'] = df['accum_count'] >= 2""",
      14892 +         params={"mult": [1.3, 1.5]},
      14893 +         direction="long",
      14894 +         lookback=35,
      14895 +         indicators=[],
      14896 +         combinable_with=["momentum", "threshold"],
      14897 +         strategy_type="SMB",
      14898 +     ),
      14899 +     # Distribution Detect
      14900 +     PatternBlock(
      14901 +         id="DISTRIBUTION_DETECT",
      14902 +         name="Distribution Detect",
      14903 +         category="smart_money",
      14904 +         formula_template="""df['range'] = df['high'] - df['low']
      14905 + df['narrow_range'] = df['range'] < df['range'].rolling(20).mean() * 0.7
      14906 + df['high_volume'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
      14907 + df['close_low'] = df['close'] < (df['high'] + df['low']) / 2
      14908 + df['distribution'] = df['narrow_range'] & df['high_volume'] & df['close_low']
      14909 + df['dist_count'] = df['distribution'].rolling(10).sum()
      14910 + df['entry_signal'] = df['dist_count'] >= 2""",
      14911 +         params={"mult": [1.3, 1.5]},
      14912 +         direction="short",
      14913 +         lookback=35,
      14914 +         indicators=[],
      14915 +         combinable_with=["momentum", "threshold"],
      14916 +         strategy_type="SMB",
      14917 +     ),
      14918 +     # Institutional Volume
      14919 +     PatternBlock(
      14920 +         id="INSTITUTIONAL_VOL",
      14921 +         name="Institutional Volume",
      14922 +         category="smart_money",
      14923 +         formula_template="""df['vol_ma'] = df['volume'].rolling(20).mean()
      14924 + df['vol_std'] = df['volume'].rolling(20).std()
      14925 + df['vol_zscore'] = (df['volume'] - df['vol_ma']) / df['vol_std']
      14926 + df['inst_vol'] = df['vol_zscore'] > {threshold}
      14927 + df['bullish_bar'] = df['close'] > df['open']
      14928 + df['body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 0.0001)
      14929 + df['strong_body'] = df['body_ratio'] > 0.6
      14930 + df['entry_signal'] = df['inst_vol'] & df['bullish_bar'] & df['strong_body']""",
      14931 +         params={"threshold": [2.0, 2.5]},
      14932 +         direction="long",
      14933 +         lookback=30,
      14934 +         indicators=[],
      14935 +         combinable_with=["momentum", "confirmation"],
      14936 +         strategy_type="SMB",
      14937 +     ),
      14938 + ]
      14939 +
      14940 +
      14941 + # =============================================================================
      14942   # ALL BLOCKS COMBINED
      14943   # =============================================================================
      14944

● Search(pattern: "BREAKOUT_STRENGTH_BLOCKS$", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 30 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      15147       + CANDLE_MOMENTUM_BLOCKS
      15148       + SUPPORT_BOUNCE_BLOCKS
      15149       + BREAKOUT_STRENGTH_BLOCKS
      15150 +     + RESISTANCE_REJECTION_BLOCKS
      15151 +     + PULLBACK_ENTRY_BLOCKS
      15152 +     + MOMENTUM_EXHAUSTION_EXT_BLOCKS
      15153 +     + VOLUME_PROFILE_EXT_BLOCKS
      15154 +     + TREND_CHANGE_BLOCKS
      15155 +     + RANGE_BOUND_BLOCKS
      15156 +     + MULTI_TIMEFRAME_PROXY_BLOCKS
      15157 +     + PRICE_STRUCTURE_BLOCKS
      15158 +     + VOLATILITY_REGIME_EXT_BLOCKS
      15159 +     + SMART_MONEY_BLOCKS
      15160   )
      15161
      15162   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python3 << 'EOF'
      import sys…)
  ⎿  Total blocks: 748
     Categories: 213
     … +36 lines (ctrl+o to expand)

● Round 21 completato!

  Risultati:
  - Blocchi totali: 748 (+30 nuovi)
  - Categorie: 213
  - Tipi strategia: 201
  - Validazione: 200/200 strategie valide
  - Lookahead: Nessun pattern rilevato
  - Strategie stimate: ~144,368

  Nuovi blocchi aggiunti (Round 21):
  1. RESISTANCE_REJECTION_BLOCKS (RRJ): Dynamic resistance/pivot rejection/MA resistance
  2. PULLBACK_ENTRY_BLOCKS (PBE): Trend pullback/EMA pullback/Fibonacci zone
  3. MOMENTUM_EXHAUSTION_EXT_BLOCKS (MEX): RSI exhaustion/deceleration/climax reversal
  4. VOLUME_PROFILE_EXT_BLOCKS (VPX): High volume node/low volume gap/POC
  5. TREND_CHANGE_BLOCKS (TCH): MA crossover confirm/ADX shift/momentum flip
  6. RANGE_BOUND_BLOCKS (RGB): Range detection/mean reversion/channel midline
  7. MULTI_TIMEFRAME_PROXY_BLOCKS (MTF): Higher MA alignment/multi-period momentum/trend stack
  8. PRICE_STRUCTURE_BLOCKS (PST): Higher high confirm/lower low break/structure shift
  9. VOLATILITY_REGIME_EXT_BLOCKS (VRE): Vol expansion/contraction alert/regime change
  10. SMART_MONEY_BLOCKS (SMB): Accumulation/distribution/institutional volume

  Progressione sessione:
  ┌───────┬─────────┬───────────────────┐
  │ Round │ Blocchi │ Strategie stimate │
  ├───────┼─────────┼───────────────────┤
  │ 19    │ 688     │ ~135,824          │
  ├───────┼─────────┼───────────────────┤
  │ 20    │ 718     │ ~140,104          │
  ├───────┼─────────┼───────────────────┤
  │ 21    │ 748     │ ~144,368          │
  └───────┴─────────┴───────────────────┘
  Hai testato che tutto funzioni? Altre possibili migliorie? (stessi requisiti)

✻ Baked for 2m 44s

❯ hai testato che tutto funzioni?
  altre possibili migliorie? con gli stessi requisiti, cioè no modifiche al codice esistente, piena compatibilità, no diminuzione strategie
  dimmi solo

● Test Round 21: PASSATO
  - 200/200 strategie valide
  - 0 errori lookahead
  - 748 blocchi funzionanti

  ---
  Proposta Round 22 - 10 nuove categorie (30 blocchi):

  1. GAP_ANALYSIS_BLOCKS (GAX): Gap up continuation, gap fill reversal, unfilled gap breakout
  2. ORDERFLOW_PROXY_BLOCKS (OFP): Delta divergence, absorption pattern, imbalance detect
  3. LIQUIDITY_BLOCKS (LIQ): Liquidity sweep, stop hunt reversal, liquidity void
  4. CYCLE_DETECTION_BLOCKS (CYC): Cycle low, cycle high, cycle midpoint
  5. STRENGTH_WEAKNESS_BLOCKS (STW): Relative strength, weakness confirm, strength divergence
  6. PATTERN_COMPLETION_BLOCKS (PTC): Double bottom confirm, head shoulders neckline, wedge break
  7. MONEY_FLOW_EXT_BLOCKS (MFX): Chaikin MF extreme, MFI divergence, flow reversal
  8. TREND_FILTER_BLOCKS (TFL): ADX filter, MA slope filter, momentum filter
  9. ENTRY_TIMING_BLOCKS (ETM): Optimal entry, pullback timing, breakout timing
  10. EXIT_SIGNAL_BLOCKS (EXS): Profit target hit, trailing stop trigger, time exit signal

  Risultato atteso:
  - Blocchi: 748 → 778 (+30)
  - Strategie: ~144,368 → ~148,800+

  Vuoi procedere?

❯ si

● Search(pattern: "^SMART_MONEY_BLOCKS = \[", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 50 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 616 lines
      14939
      14940
      14941   # =============================================================================
      14942 + # GAP ANALYSIS BLOCKS
      14943 + # =============================================================================
      14944 +
      14945 + GAP_ANALYSIS_BLOCKS = [
      14946 +     # Gap Up Continuation
      14947 +     PatternBlock(
      14948 +         id="GAP_UP_CONT",
      14949 +         name="Gap Up Continuation",
      14950 +         category="gap_analysis",
      14951 +         formula_template="""df['gap'] = df['open'] - df['close'].shift(1)
      14952 + df['gap_pct'] = df['gap'] / df['close'].shift(1) * 100
      14953 + df['gap_up'] = df['gap_pct'] > {threshold}
      14954 + df['holds'] = df['low'] > df['close'].shift(1)
      14955 + df['bullish'] = df['close'] > df['open']
      14956 + df['entry_signal'] = df['gap_up'] & df['holds'] & df['bullish']""",
      14957 +         params={"threshold": [0.5, 1.0]},
      14958 +         direction="long",
      14959 +         lookback=10,
      14960 +         indicators=[],
      14961 +         combinable_with=["volume", "momentum"],
      14962 +         strategy_type="GAX",
      14963 +     ),
      14964 +     # Gap Fill Reversal
      14965 +     PatternBlock(
      14966 +         id="GAP_FILL_REV",
      14967 +         name="Gap Fill Reversal",
      14968 +         category="gap_analysis",
      14969 +         formula_template="""df['gap'] = df['open'] - df['close'].shift(1)
      14970 + df['gap_pct'] = df['gap'] / df['close'].shift(1) * 100
      14971 + df['gap_down'] = df['gap_pct'] < -{threshold}
      14972 + df['filled'] = df['high'] >= df['close'].shift(1)
      14973 + df['reversal'] = df['close'] > df['open']
      14974 + df['entry_signal'] = df['gap_down'] & df['filled'] & df['reversal']""",
      14975 +         params={"threshold": [0.5, 1.0]},
      14976 +         direction="long",
      14977 +         lookback=10,
      14978 +         indicators=[],
      14979 +         combinable_with=["volume", "confirmation"],
      14980 +         strategy_type="GAX",
      14981 +     ),
      14982 +     # Unfilled Gap Breakout
      14983 +     PatternBlock(
      14984 +         id="UNFILLED_GAP_BREAK",
      14985 +         name="Unfilled Gap Breakout",
      14986 +         category="gap_analysis",
      14987 +         formula_template="""df['gap'] = df['open'] - df['close'].shift(1)
      14988 + df['gap_pct'] = df['gap'] / df['close'].shift(1) * 100
      14989 + df['gap_up'] = df['gap_pct'] > 0.3
      14990 + df['unfilled'] = df['low'].rolling(5).min() > df['close'].shift(6)
      14991 + df['break_high'] = df['close'] > df['high'].shift(1).rolling(3).max()
      14992 + df['entry_signal'] = df['unfilled'] & df['break_high']""",
      14993 +         params={},
      14994 +         direction="long",
      14995 +         lookback=15,
      14996 +         indicators=[],
      14997 +         combinable_with=["momentum", "threshold"],
      14998 +         strategy_type="GAX",
      14999 +     ),
      15000 + ]
      15001 +
      15002 +
      15003 + # =============================================================================
      15004 + # ORDERFLOW PROXY BLOCKS
      15005 + # =============================================================================
      15006 +
      15007 + ORDERFLOW_PROXY_BLOCKS = [
      15008 +     # Delta Divergence
      15009 +     PatternBlock(
      15010 +         id="DELTA_DIV",
      15011 +         name="Delta Divergence",
      15012 +         category="orderflow_proxy",
      15013 +         formula_template="""df['delta'] = (df['close'] - df['open']) * df['volume']
      15014 + df['cum_delta'] = df['delta'].rolling({period}).sum()
      15015 + df['price_down'] = df['close'] < df['close'].shift({period})
      15016 + df['delta_up'] = df['cum_delta'] > df['cum_delta'].shift({period})
      15017 + df['divergence'] = df['price_down'] & df['delta_up']
      15018 + df['entry_signal'] = df['divergence']""",
      15019 +         params={"period": [10, 14]},
      15020 +         direction="long",
      15021 +         lookback=25,
      15022 +         indicators=[],
      15023 +         combinable_with=["volume", "momentum"],
      15024 +         strategy_type="OFP",
      15025 +     ),
      15026 +     # Absorption Pattern
      15027 +     PatternBlock(
      15028 +         id="ABSORPTION_PATTERN",
      15029 +         name="Absorption Pattern",
      15030 +         category="orderflow_proxy",
      15031 +         formula_template="""df['range'] = df['high'] - df['low']
      15032 + df['body'] = abs(df['close'] - df['open'])
      15033 + df['small_body'] = df['body'] < df['range'] * 0.3
      15034 + df['high_vol'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
      15035 + df['absorption'] = df['small_body'] & df['high_vol']
      15036 + df['next_bullish'] = df['close'] > df['open']
      15037 + df['entry_signal'] = df['absorption'].shift(1) & df['next_bullish']""",
      15038 +         params={"mult": [1.5, 2.0]},
      15039 +         direction="long",
      15040 +         lookback=25,
      15041 +         indicators=[],
      15042 +         combinable_with=["momentum", "confirmation"],
      15043 +         strategy_type="OFP",
      15044 +     ),
      15045 +     # Imbalance Detect
      15046 +     PatternBlock(
      15047 +         id="IMBALANCE_DETECT",
      15048 +         name="Imbalance Detect",
      15049 +         category="orderflow_proxy",
      15050 +         formula_template="""df['up_vol'] = df['volume'].where(df['close'] > df['open'], 0)
      15051 + df['dn_vol'] = df['volume'].where(df['close'] < df['open'], 0)
      15052 + df['vol_ratio'] = df['up_vol'].rolling({period}).sum() / (df['dn_vol'].rolling({period}).sum() + 1)
      15053 + df['imbalance'] = df['vol_ratio'] > {threshold}
      15054 + df['trend_up'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
      15055 + df['entry_signal'] = df['imbalance'] & df['trend_up']""",
      15056 +         params={"period": [10], "threshold": [1.5, 2.0]},
      15057 +         direction="long",
      15058 +         lookback=30,
      15059 +         indicators=["EMA"],
      15060 +         combinable_with=["momentum", "threshold"],
      15061 +         strategy_type="OFP",
      15062 +     ),
      15063 + ]
      15064 +
      15065 +
      15066 + # =============================================================================
      15067 + # LIQUIDITY BLOCKS
      15068 + # =============================================================================
      15069 +
      15070 + LIQUIDITY_BLOCKS = [
      15071 +     # Liquidity Sweep
      15072 +     PatternBlock(
      15073 +         id="LIQUIDITY_SWEEP",
      15074 +         name="Liquidity Sweep",
      15075 +         category="liquidity",
      15076 +         formula_template="""df['prev_low'] = df['low'].shift(1).rolling({period}).min()
      15077 + df['sweep'] = df['low'] < df['prev_low']
      15078 + df['reclaim'] = df['close'] > df['prev_low']
      15079 + df['vol_spike'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
      15080 + df['entry_signal'] = df['sweep'] & df['reclaim'] & df['vol_spike']""",
      15081 +         params={"period": [10, 20]},
      15082 +         direction="long",
      15083 +         lookback=30,
      15084 +         indicators=[],
      15085 +         combinable_with=["momentum", "confirmation"],
      15086 +         strategy_type="LIQ",
      15087 +     ),
      15088 +     # Stop Hunt Reversal
      15089 +     PatternBlock(
      15090 +         id="STOP_HUNT_REV",
      15091 +         name="Stop Hunt Reversal",
      15092 +         category="liquidity",
      15093 +         formula_template="""df['low_20'] = df['low'].rolling(20).min()
      15094 + df['break_low'] = df['low'] < df['low_20'].shift(1)
      15095 + df['wick'] = df['close'] - df['low']
      15096 + df['body'] = abs(df['close'] - df['open'])
      15097 + df['long_wick'] = df['wick'] > df['body'] * {mult}
      15098 + df['bullish_close'] = df['close'] > df['open']
      15099 + df['entry_signal'] = df['break_low'] & df['long_wick'] & df['bullish_close']""",
      15100 +         params={"mult": [2.0, 3.0]},
      15101 +         direction="long",
      15102 +         lookback=25,
      15103 +         indicators=[],
      15104 +         combinable_with=["volume", "momentum"],
      15105 +         strategy_type="LIQ",
      15106 +     ),
      15107 +     # Liquidity Void
      15108 +     PatternBlock(
      15109 +         id="LIQUIDITY_VOID",
      15110 +         name="Liquidity Void",
      15111 +         category="liquidity",
      15112 +         formula_template="""df['gap'] = df['low'] - df['high'].shift(1)
      15113 + df['void'] = df['gap'] > df['close'].shift(1) * 0.005
      15114 + df['void_fill'] = df['low'] <= df['high'].shift(2)
      15115 + df['bullish'] = df['close'] > df['open']
      15116 + df['entry_signal'] = df['void'].shift(1) & df['void_fill'] & df['bullish']""",
      15117 +         params={},
      15118 +         direction="long",
      15119 +         lookback=10,
      15120 +         indicators=[],
      15121 +         combinable_with=["volume", "confirmation"],
      15122 +         strategy_type="LIQ",
      15123 +     ),
      15124 + ]
      15125 +
      15126 +
      15127 + # =============================================================================
      15128 + # CYCLE DETECTION BLOCKS
      15129 + # =============================================================================
      15130 +
      15131 + CYCLE_DETECTION_BLOCKS = [
      15132 +     # Cycle Low
      15133 +     PatternBlock(
      15134 +         id="CYCLE_LOW",
      15135 +         name="Cycle Low",
      15136 +         category="cycle_detection",
      15137 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      15138 + df['rsi_low'] = df['rsi'].rolling({period}).min()
      15139 + df['at_cycle_low'] = df['rsi'] <= df['rsi_low'] * 1.05
      15140 + df['turning'] = df['rsi'] > df['rsi'].shift(1)
      15141 + df['price_support'] = df['close'] > df['low'].rolling(10).min()
      15142 + df['entry_signal'] = df['at_cycle_low'] & df['turning'] & df['price_support']""",
      15143 +         params={"period": [20, 30]},
      15144 +         direction="long",
      15145 +         lookback=40,
      15146 +         indicators=["RSI"],
      15147 +         combinable_with=["volume", "confirmation"],
      15148 +         strategy_type="CYC",
      15149 +     ),
      15150 +     # Cycle High
      15151 +     PatternBlock(
      15152 +         id="CYCLE_HIGH",
      15153 +         name="Cycle High",
      15154 +         category="cycle_detection",
      15155 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      15156 + df['rsi_high'] = df['rsi'].rolling({period}).max()
      15157 + df['at_cycle_high'] = df['rsi'] >= df['rsi_high'] * 0.95
      15158 + df['turning'] = df['rsi'] < df['rsi'].shift(1)
      15159 + df['price_resist'] = df['close'] < df['high'].rolling(10).max()
      15160 + df['entry_signal'] = df['at_cycle_high'] & df['turning'] & df['price_resist']""",
      15161 +         params={"period": [20, 30]},
      15162 +         direction="short",
      15163 +         lookback=40,
      15164 +         indicators=["RSI"],
      15165 +         combinable_with=["volume", "confirmation"],
      15166 +         strategy_type="CYC",
      15167 +     ),
      15168 +     # Cycle Midpoint
      15169 +     PatternBlock(
      15170 +         id="CYCLE_MIDPOINT",
      15171 +         name="Cycle Midpoint",
      15172 +         category="cycle_detection",
      15173 +         formula_template="""df['high_p'] = df['high'].rolling({period}).max()
      15174 + df['low_p'] = df['low'].rolling({period}).min()
      15175 + df['midpoint'] = (df['high_p'] + df['low_p']) / 2
      15176 + df['cross_up'] = (df['close'] > df['midpoint']) & (df['close'].shift(1) <= df['midpoint'].shift(1))
      15177 + df['momentum'] = df['close'] > df['close'].shift(3)
      15178 + df['entry_signal'] = df['cross_up'] & df['momentum']""",
      15179 +         params={"period": [20]},
      15180 +         direction="long",
      15181 +         lookback=30,
      15182 +         indicators=[],
      15183 +         combinable_with=["momentum", "threshold"],
      15184 +         strategy_type="CYC",
      15185 +     ),
      15186 + ]
      15187 +
      15188 +
      15189 + # =============================================================================
      15190 + # STRENGTH WEAKNESS BLOCKS
      15191 + # =============================================================================
      15192 +
      15193 + STRENGTH_WEAKNESS_BLOCKS = [
      15194 +     # Relative Strength
      15195 +     PatternBlock(
      15196 +         id="RELATIVE_STRENGTH",
      15197 +         name="Relative Strength",
      15198 +         category="strength_weakness",
      15199 +         formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
      15200 + df['roc_ma'] = df['roc'].rolling(20).mean()
      15201 + df['strong'] = df['roc'] > df['roc_ma'] * {mult}
      15202 + df['trend_up'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
      15203 + df['entry_signal'] = df['strong'] & df['trend_up']""",
      15204 +         params={"period": [10], "mult": [1.5, 2.0]},
      15205 +         direction="long",
      15206 +         lookback=35,
      15207 +         indicators=["ROC", "EMA"],
      15208 +         combinable_with=["volume", "momentum"],
      15209 +         strategy_type="STW",
      15210 +     ),
      15211 +     # Weakness Confirm
      15212 +     PatternBlock(
      15213 +         id="WEAKNESS_CONFIRM",
      15214 +         name="Weakness Confirm",
      15215 +         category="strength_weakness",
      15216 +         formula_template="""df['roc'] = ta.ROC(df['close'], timeperiod={period})
      15217 + df['weak'] = df['roc'] < -{threshold}
      15218 + df['trend_down'] = df['close'] < ta.EMA(df['close'], timeperiod=20)
      15219 + df['vol_up'] = df['volume'] > df['volume'].rolling(20).mean()
      15220 + df['entry_signal'] = df['weak'] & df['trend_down'] & df['vol_up']""",
      15221 +         params={"period": [10], "threshold": [2, 3]},
      15222 +         direction="short",
      15223 +         lookback=35,
      15224 +         indicators=["ROC", "EMA"],
      15225 +         combinable_with=["momentum", "confirmation"],
      15226 +         strategy_type="STW",
      15227 +     ),
      15228 +     # Strength Divergence
      15229 +     PatternBlock(
      15230 +         id="STRENGTH_DIV",
      15231 +         name="Strength Divergence",
      15232 +         category="strength_weakness",
      15233 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      15234 + df['price_higher'] = df['close'] > df['close'].shift(10)
      15235 + df['rsi_lower'] = df['rsi'] < df['rsi'].shift(10)
      15236 + df['bearish_div'] = df['price_higher'] & df['rsi_lower']
      15237 + df['overbought'] = df['rsi'] > 60
      15238 + df['entry_signal'] = df['bearish_div'] & df['overbought']""",
      15239 +         params={},
      15240 +         direction="short",
      15241 +         lookback=25,
      15242 +         indicators=["RSI"],
      15243 +         combinable_with=["volume", "threshold"],
      15244 +         strategy_type="STW",
      15245 +     ),
      15246 + ]
      15247 +
      15248 +
      15249 + # =============================================================================
      15250 + # PATTERN COMPLETION BLOCKS
      15251 + # =============================================================================
      15252 +
      15253 + PATTERN_COMPLETION_BLOCKS = [
      15254 +     # Double Bottom Confirm
      15255 +     PatternBlock(
      15256 +         id="DOUBLE_BOTTOM_CONFIRM",
      15257 +         name="Double Bottom Confirm",
      15258 +         category="pattern_completion",
      15259 +         formula_template="""df['low_10'] = df['low'].rolling(10).min()
      15260 + df['first_low'] = df['low_10'].shift(10)
      15261 + df['second_low'] = df['low_10']
      15262 + df['similar'] = abs(df['second_low'] - df['first_low']) / df['close'] < 0.02
      15263 + df['neckline'] = df['high'].shift(5).rolling(5).max()
      15264 + df['break_neck'] = df['close'] > df['neckline']
      15265 + df['entry_signal'] = df['similar'] & df['break_neck']""",
      15266 +         params={},
      15267 +         direction="long",
      15268 +         lookback=30,
      15269 +         indicators=[],
      15270 +         combinable_with=["volume", "confirmation"],
      15271 +         strategy_type="PTC",
      15272 +     ),
      15273 +     # Head Shoulders Neckline
      15274 +     PatternBlock(
      15275 +         id="HS_NECKLINE",
      15276 +         name="Head Shoulders Neckline",
      15277 +         category="pattern_completion",
      15278 +         formula_template="""df['high_20'] = df['high'].rolling(20).max()
      15279 + df['was_high'] = df['high'].shift(10) >= df['high_20'].shift(10) * 0.98
      15280 + df['lower_now'] = df['high'] < df['high'].shift(10) * 0.95
      15281 + df['neckline'] = df['low'].shift(5).rolling(10).min()
      15282 + df['break_neck'] = df['close'] < df['neckline']
      15283 + df['entry_signal'] = df['was_high'] & df['lower_now'] & df['break_neck']""",
      15284 +         params={},
      15285 +         direction="short",
      15286 +         lookback=35,
      15287 +         indicators=[],
      15288 +         combinable_with=["volume", "momentum"],
      15289 +         strategy_type="PTC",
      15290 +     ),
      15291 +     # Wedge Break
      15292 +     PatternBlock(
      15293 +         id="WEDGE_BREAK",
      15294 +         name="Wedge Break",
      15295 +         category="pattern_completion",
      15296 +         formula_template="""df['high_slope'] = (df['high'] - df['high'].shift({period})) / {period}
      15297 + df['low_slope'] = (df['low'] - df['low'].shift({period})) / {period}
      15298 + df['converging'] = df['high_slope'] < df['low_slope']
      15299 + df['wedge'] = df['converging'].rolling(5).sum() >= 3
      15300 + df['break_up'] = df['close'] > df['high'].shift(1).rolling(5).max()
      15301 + df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
      15302 + df['entry_signal'] = df['wedge'].shift(1) & df['break_up'] & df['vol_surge']""",
      15303 +         params={"period": [10]},
      15304 +         direction="long",
      15305 +         lookback=25,
      15306 +         indicators=[],
      15307 +         combinable_with=["momentum", "confirmation"],
      15308 +         strategy_type="PTC",
      15309 +     ),
      15310 + ]
      15311 +
      15312 +
      15313 + # =============================================================================
      15314 + # MONEY FLOW EXTENDED BLOCKS
      15315 + # =============================================================================
      15316 +
      15317 + MONEY_FLOW_EXT_BLOCKS = [
      15318 +     # Chaikin MF Extreme
      15319 +     PatternBlock(
      15320 +         id="CMF_EXTREME",
      15321 +         name="Chaikin MF Extreme",
      15322 +         category="money_flow_ext",
      15323 +         formula_template="""df['mfm'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'] +
            +0.0001)
      15324 + df['mfv'] = df['mfm'] * df['volume']
      15325 + df['cmf'] = df['mfv'].rolling({period}).sum() / df['volume'].rolling({period}).sum()
      15326 + df['extreme_low'] = df['cmf'] < -{threshold}
      15327 + df['turning'] = df['cmf'] > df['cmf'].shift(1)
      15328 + df['entry_signal'] = df['extreme_low'] & df['turning']""",
      15329 +         params={"period": [20], "threshold": [0.2, 0.25]},
      15330 +         direction="long",
      15331 +         lookback=30,
      15332 +         indicators=[],
      15333 +         combinable_with=["volume", "momentum"],
      15334 +         strategy_type="MFX",
      15335 +     ),
      15336 +     # MFI Divergence
      15337 +     PatternBlock(
      15338 +         id="MFI_DIV",
      15339 +         name="MFI Divergence",
      15340 +         category="money_flow_ext",
      15341 +         formula_template="""df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
      15342 + df['price_lower'] = df['close'] < df['close'].shift({period})
      15343 + df['mfi_higher'] = df['mfi'] > df['mfi'].shift({period})
      15344 + df['bullish_div'] = df['price_lower'] & df['mfi_higher']
      15345 + df['entry_signal'] = df['bullish_div']""",
      15346 +         params={"period": [10, 14]},
      15347 +         direction="long",
      15348 +         lookback=25,
      15349 +         indicators=["MFI"],
      15350 +         combinable_with=["momentum", "confirmation"],
      15351 +         strategy_type="MFX",
      15352 +     ),
      15353 +     # Flow Reversal
      15354 +     PatternBlock(
      15355 +         id="FLOW_REVERSAL",
      15356 +         name="Flow Reversal",
      15357 +         category="money_flow_ext",
      15358 +         formula_template="""df['mfi'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
      15359 + df['was_oversold'] = df['mfi'].shift(3) < 20
      15360 + df['recovering'] = df['mfi'] > 30
      15361 + df['price_up'] = df['close'] > df['close'].shift(3)
      15362 + df['entry_signal'] = df['was_oversold'] & df['recovering'] & df['price_up']""",
      15363 +         params={},
      15364 +         direction="long",
      15365 +         lookback=25,
      15366 +         indicators=["MFI"],
      15367 +         combinable_with=["volume", "threshold"],
      15368 +         strategy_type="MFX",
      15369 +     ),
      15370 + ]
      15371 +
      15372 +
      15373 + # =============================================================================
      15374 + # TREND FILTER BLOCKS
      15375 + # =============================================================================
      15376 +
      15377 + TREND_FILTER_BLOCKS = [
      15378 +     # ADX Filter
      15379 +     PatternBlock(
      15380 +         id="ADX_FILTER",
      15381 +         name="ADX Filter",
      15382 +         category="trend_filter",
      15383 +         formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
      15384 + df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
      15385 + df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
      15386 + df['trending'] = df['adx'] > {threshold}
      15387 + df['bullish'] = df['plus_di'] > df['minus_di']
      15388 + df['entry_signal'] = df['trending'] & df['bullish']""",
      15389 +         params={"threshold": [20, 25]},
      15390 +         direction="long",
      15391 +         lookback=25,
      15392 +         indicators=["ADX", "PLUS_DI", "MINUS_DI"],
      15393 +         combinable_with=["momentum", "volume"],
      15394 +         strategy_type="TFL",
      15395 +     ),
      15396 +     # MA Slope Filter
      15397 +     PatternBlock(
      15398 +         id="MA_SLOPE_FILTER",
      15399 +         name="MA Slope Filter",
      15400 +         category="trend_filter",
      15401 +         formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
      15402 + df['slope'] = (df['ema'] - df['ema'].shift(5)) / df['ema'].shift(5) * 100
      15403 + df['strong_slope'] = df['slope'] > {threshold}
      15404 + df['price_above'] = df['close'] > df['ema']
      15405 + df['entry_signal'] = df['strong_slope'] & df['price_above']""",
      15406 +         params={"period": [20], "threshold": [0.5, 1.0]},
      15407 +         direction="long",
      15408 +         lookback=35,
      15409 +         indicators=["EMA"],
      15410 +         combinable_with=["momentum", "confirmation"],
      15411 +         strategy_type="TFL",
      15412 +     ),
      15413 +     # Momentum Filter
      15414 +     PatternBlock(
      15415 +         id="MOMENTUM_FILTER",
      15416 +         name="Momentum Filter",
      15417 +         category="trend_filter",
      15418 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      15419 + df['macd'], _, df['macd_hist'] = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
      15420 + df['rsi_bullish'] = df['rsi'] > 50
      15421 + df['macd_bullish'] = df['macd_hist'] > 0
      15422 + df['price_up'] = df['close'] > df['close'].shift(5)
      15423 + df['entry_signal'] = df['rsi_bullish'] & df['macd_bullish'] & df['price_up']""",
      15424 +         params={},
      15425 +         direction="long",
      15426 +         lookback=35,
      15427 +         indicators=["RSI", "MACD"],
      15428 +         combinable_with=["volume", "threshold"],
      15429 +         strategy_type="TFL",
      15430 +     ),
      15431 + ]
      15432 +
      15433 +
      15434 + # =============================================================================
      15435 + # ENTRY TIMING BLOCKS
      15436 + # =============================================================================
      15437 +
      15438 + ENTRY_TIMING_BLOCKS = [
      15439 +     # Optimal Entry
      15440 +     PatternBlock(
      15441 +         id="OPTIMAL_ENTRY",
      15442 +         name="Optimal Entry",
      15443 +         category="entry_timing",
      15444 +         formula_template="""df['ema20'] = ta.EMA(df['close'], timeperiod=20)
      15445 + df['ema50'] = ta.EMA(df['close'], timeperiod=50)
      15446 + df['uptrend'] = df['ema20'] > df['ema50']
      15447 + df['pullback'] = df['close'] < df['ema20'] * 1.01
      15448 + df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      15449 + df['not_oversold'] = df['rsi'] > 35
      15450 + df['bounce'] = df['close'] > df['close'].shift(1)
      15451 + df['entry_signal'] = df['uptrend'] & df['pullback'] & df['not_oversold'] & df['bounce']""",
      15452 +         params={},
      15453 +         direction="long",
      15454 +         lookback=60,
      15455 +         indicators=["EMA", "RSI"],
      15456 +         combinable_with=["volume", "confirmation"],
      15457 +         strategy_type="ETM",
      15458 +     ),
      15459 +     # Pullback Timing
      15460 +     PatternBlock(
      15461 +         id="PULLBACK_TIMING",
      15462 +         name="Pullback Timing",
      15463 +         category="entry_timing",
      15464 +         formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod={period})
      15465 + df['distance'] = (df['close'] - df['ema']) / df['ema'] * 100
      15466 + df['was_extended'] = df['distance'].shift(3) > 2
      15467 + df['returned'] = abs(df['distance']) < 0.5
      15468 + df['bounce'] = df['close'] > df['open']
      15469 + df['entry_signal'] = df['was_extended'] & df['returned'] & df['bounce']""",
      15470 +         params={"period": [20, 50]},
      15471 +         direction="long",
      15472 +         lookback=60,
      15473 +         indicators=["EMA"],
      15474 +         combinable_with=["momentum", "threshold"],
      15475 +         strategy_type="ETM",
      15476 +     ),
      15477 +     # Breakout Timing
      15478 +     PatternBlock(
      15479 +         id="BREAKOUT_TIMING",
      15480 +         name="Breakout Timing",
      15481 +         category="entry_timing",
      15482 +         formula_template="""df['high_20'] = df['high'].rolling(20).max()
      15483 + df['break'] = df['close'] > df['high_20'].shift(1)
      15484 + df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
      15485 + df['strong_close'] = df['close'] > (df['high'] + df['low']) / 2
      15486 + df['entry_signal'] = df['break'] & df['vol_confirm'] & df['strong_close']""",
      15487 +         params={"mult": [1.5, 2.0]},
      15488 +         direction="long",
      15489 +         lookback=30,
      15490 +         indicators=[],
      15491 +         combinable_with=["momentum", "confirmation"],
      15492 +         strategy_type="ETM",
      15493 +     ),
      15494 + ]
      15495 +
      15496 +
      15497 + # =============================================================================
      15498 + # EXIT SIGNAL BLOCKS
      15499 + # =============================================================================
      15500 +
      15501 + EXIT_SIGNAL_BLOCKS = [
      15502 +     # Profit Target Hit
      15503 +     PatternBlock(
      15504 +         id="PROFIT_TARGET",
      15505 +         name="Profit Target Hit",
      15506 +         category="exit_signal",
      15507 +         formula_template="""df['entry_price'] = df['close'].shift({lookback})
      15508 + df['profit_pct'] = (df['close'] - df['entry_price']) / df['entry_price'] * 100
      15509 + df['target_hit'] = df['profit_pct'] >= {target}
      15510 + df['momentum_fading'] = ta.RSI(df['close'], timeperiod=14) > 70
      15511 + df['entry_signal'] = df['target_hit'] & df['momentum_fading']""",
      15512 +         params={"lookback": [10], "target": [3, 5]},
      15513 +         direction="short",
      15514 +         lookback=25,
      15515 +         indicators=["RSI"],
      15516 +         combinable_with=["momentum", "threshold"],
      15517 +         strategy_type="EXS",
      15518 +     ),
      15519 +     # Trailing Stop Trigger
      15520 +     PatternBlock(
      15521 +         id="TRAIL_STOP_TRIGGER",
      15522 +         name="Trailing Stop Trigger",
      15523 +         category="exit_signal",
      15524 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
      15525 + df['high_since'] = df['high'].rolling({period}).max()
      15526 + df['trail_stop'] = df['high_since'] - df['atr'] * {mult}
      15527 + df['stop_hit'] = df['close'] < df['trail_stop']
      15528 + df['was_profit'] = df['high_since'] > df['close'].shift({period}) * 1.02
      15529 + df['entry_signal'] = df['stop_hit'] & df['was_profit']""",
      15530 +         params={"period": [10], "mult": [2.0, 3.0]},
      15531 +         direction="short",
      15532 +         lookback=25,
      15533 +         indicators=["ATR"],
      15534 +         combinable_with=["momentum", "confirmation"],
      15535 +         strategy_type="EXS",
      15536 +     ),
      15537 +     # Time Exit Signal
      15538 +     PatternBlock(
      15539 +         id="TIME_EXIT_SIGNAL",
      15540 +         name="Time Exit Signal",
      15541 +         category="exit_signal",
      15542 +         formula_template="""df['bars_since_high'] = df['high'].rolling({period}).apply(lambda x: {period} - 1 - x.argmax(),
            +raw=True)
      15543 + df['stale'] = df['bars_since_high'] >= {period} - 2
      15544 + df['momentum_lost'] = ta.RSI(df['close'], timeperiod=14) < 50
      15545 + df['below_ma'] = df['close'] < ta.EMA(df['close'], timeperiod=20)
      15546 + df['entry_signal'] = df['stale'] & df['momentum_lost'] & df['below_ma']""",
      15547 +         params={"period": [10, 20]},
      15548 +         direction="short",
      15549 +         lookback=30,
      15550 +         indicators=["RSI", "EMA"],
      15551 +         combinable_with=["volume", "threshold"],
      15552 +         strategy_type="EXS",
      15553 +     ),
      15554 + ]
      15555 +
      15556 +
      15557 + # =============================================================================
      15558   # ALL BLOCKS COMBINED
      15559   # =============================================================================
      15560

● Search(pattern: "SMART_MONEY_BLOCKS$", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 20 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      15773       + PRICE_STRUCTURE_BLOCKS
      15774       + VOLATILITY_REGIME_EXT_BLOCKS
      15775       + SMART_MONEY_BLOCKS
      15776 +     + GAP_ANALYSIS_BLOCKS
      15777 +     + ORDERFLOW_PROXY_BLOCKS
      15778 +     + LIQUIDITY_BLOCKS
      15779 +     + CYCLE_DETECTION_BLOCKS
      15780 +     + STRENGTH_WEAKNESS_BLOCKS
      15781 +     + PATTERN_COMPLETION_BLOCKS
      15782 +     + MONEY_FLOW_EXT_BLOCKS
      15783 +     + TREND_FILTER_BLOCKS
      15784 +     + ENTRY_TIMING_BLOCKS
      15785 +     + EXIT_SIGNAL_BLOCKS
      15786   )
      15787
      15788   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python3 << 'EOF'
      import sys…)
  ⎿  Total blocks: 778
     Categories: 223
     … +36 lines (ctrl+o to expand)

● Round 22 completato!

  Risultati:
  - Blocchi totali: 778 (+30 nuovi)
  - Categorie: 223
  - Tipi strategia: 211
  - Validazione: 200/200 strategie valide
  - Lookahead: Nessun pattern rilevato
  - Strategie stimate: ~148,680

  Nuovi blocchi aggiunti (Round 22):
  1. GAP_ANALYSIS_BLOCKS (GAX): Gap up continuation/fill reversal/unfilled breakout
  2. ORDERFLOW_PROXY_BLOCKS (OFP): Delta divergence/absorption/imbalance detect
  3. LIQUIDITY_BLOCKS (LIQ): Liquidity sweep/stop hunt reversal/void
  4. CYCLE_DETECTION_BLOCKS (CYC): Cycle low/high/midpoint
  5. STRENGTH_WEAKNESS_BLOCKS (STW): Relative strength/weakness confirm/divergence
  6. PATTERN_COMPLETION_BLOCKS (PTC): Double bottom/head shoulders/wedge break
  7. MONEY_FLOW_EXT_BLOCKS (MFX): Chaikin extreme/MFI divergence/flow reversal
  8. TREND_FILTER_BLOCKS (TFL): ADX filter/MA slope/momentum filter
  9. ENTRY_TIMING_BLOCKS (ETM): Optimal entry/pullback timing/breakout timing
  10. EXIT_SIGNAL_BLOCKS (EXS): Profit target/trailing stop/time exit

  Progressione sessione:
  ┌───────┬─────────┬───────────────────┐
  │ Round │ Blocchi │ Strategie stimate │
  ├───────┼─────────┼───────────────────┤
  │ 20    │ 718     │ ~140,104          │
  ├───────┼─────────┼───────────────────┤
  │ 21    │ 748     │ ~144,368          │
  ├───────┼─────────┼───────────────────┤
  │ 22    │ 778     │ ~148,680          │
  └───────┴─────────┴───────────────────┘
  Hai testato che tutto funzioni? Altre possibili migliorie? (stessi requisiti)

✻ Cogitated for 2m 42s

❯ hai testato che tutto funzioni?
  altre possibili migliorie? con gli stessi requisiti, cioè no modifiche al codice esistente, piena compatibilità, no diminuzione strategie
  dimmi solo

● Test Round 22: PASSATO
  - 200/200 strategie valide
  - 0 errori lookahead
  - 778 blocchi funzionanti

  ---
  Proposta Round 23 - 10 nuove categorie (30 blocchi):

  1. MARKET_REGIME_BLOCKS (MRG): Trending regime, ranging regime, volatile regime
  2. PRICE_EFFICIENCY_BLOCKS (PEF): Efficiency ratio signal, fractal efficiency, noise filter
  3. VOLUME_CLIMAX_EXT_BLOCKS (VCX): Buying climax, selling climax, exhaustion volume
  4. REVERSAL_CONFIRM_BLOCKS (RVC): Pin bar confirm, engulfing confirm, key reversal
  5. CONTINUATION_PATTERN_BLOCKS (CNP): Flag breakout, pennant break, triangle break
  6. OSCILLATOR_CROSS_EXT_BLOCKS (OCX): RSI cross 50, Stoch cross, CCI zero cross
  7. MA_SYSTEM_BLOCKS (MAS2): Triple MA system, ribbon expansion, MA squeeze
  8. PRICE_LEVEL_BLOCKS (PLV): Round number, psychological level, pivot cluster
  9. VOLATILITY_SQUEEZE_EXT_BLOCKS (VSQ): Keltner squeeze, BB squeeze signal, ATR squeeze
  10. SENTIMENT_PROXY_BLOCKS (SNT): Fear extreme, greed extreme, sentiment flip

  Risultato atteso:
  - Blocchi: 778 → 808 (+30)
  - Strategie: ~148,680 → ~153,000+

  Vuoi procedere?

❯ si

● Search(pattern: "^EXIT_SIGNAL_BLOCKS = \[", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 50 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 624 lines
      15555
      15556
      15557   # =============================================================================
      15558 + # MARKET REGIME BLOCKS
      15559 + # =============================================================================
      15560 +
      15561 + MARKET_REGIME_BLOCKS = [
      15562 +     # Trending Regime
      15563 +     PatternBlock(
      15564 +         id="TRENDING_REGIME",
      15565 +         name="Trending Regime",
      15566 +         category="market_regime",
      15567 +         formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
      15568 + df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
      15569 + df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
      15570 + df['trending'] = df['adx'] > {threshold}
      15571 + df['bullish_trend'] = df['plus_di'] > df['minus_di']
      15572 + df['adx_rising'] = df['adx'] > df['adx'].shift(3)
      15573 + df['entry_signal'] = df['trending'] & df['bullish_trend'] & df['adx_rising']""",
      15574 +         params={"threshold": [25, 30]},
      15575 +         direction="long",
      15576 +         lookback=25,
      15577 +         indicators=["ADX", "PLUS_DI", "MINUS_DI"],
      15578 +         combinable_with=["momentum", "volume"],
      15579 +         strategy_type="MRG",
      15580 +     ),
      15581 +     # Ranging Regime
      15582 +     PatternBlock(
      15583 +         id="RANGING_REGIME",
      15584 +         name="Ranging Regime",
      15585 +         category="market_regime",
      15586 +         formula_template="""df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
      15587 + df['ranging'] = df['adx'] < {threshold}
      15588 + df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      15589 + df['oversold'] = df['rsi'] < 35
      15590 + df['bounce'] = df['close'] > df['close'].shift(1)
      15591 + df['entry_signal'] = df['ranging'] & df['oversold'] & df['bounce']""",
      15592 +         params={"threshold": [20, 25]},
      15593 +         direction="long",
      15594 +         lookback=25,
      15595 +         indicators=["ADX", "RSI"],
      15596 +         combinable_with=["volume", "threshold"],
      15597 +         strategy_type="MRG",
      15598 +     ),
      15599 +     # Volatile Regime
      15600 +     PatternBlock(
      15601 +         id="VOLATILE_REGIME",
      15602 +         name="Volatile Regime",
      15603 +         category="market_regime",
      15604 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
      15605 + df['atr_ma'] = df['atr'].rolling(20).mean()
      15606 + df['volatile'] = df['atr'] > df['atr_ma'] * {mult}
      15607 + df['direction'] = df['close'] > ta.EMA(df['close'], timeperiod=20)
      15608 + df['momentum'] = df['close'] > df['close'].shift(3)
      15609 + df['entry_signal'] = df['volatile'] & df['direction'] & df['momentum']""",
      15610 +         params={"mult": [1.5, 2.0]},
      15611 +         direction="long",
      15612 +         lookback=35,
      15613 +         indicators=["ATR", "EMA"],
      15614 +         combinable_with=["momentum", "confirmation"],
      15615 +         strategy_type="MRG",
      15616 +     ),
      15617 + ]
      15618 +
      15619 +
      15620 + # =============================================================================
      15621 + # PRICE EFFICIENCY BLOCKS
      15622 + # =============================================================================
      15623 +
      15624 + PRICE_EFFICIENCY_BLOCKS = [
      15625 +     # Efficiency Ratio Signal
      15626 +     PatternBlock(
      15627 +         id="EFFICIENCY_SIGNAL",
      15628 +         name="Efficiency Ratio Signal",
      15629 +         category="price_efficiency",
      15630 +         formula_template="""df['change'] = abs(df['close'] - df['close'].shift({period}))
      15631 + df['volatility'] = df['close'].diff().abs().rolling({period}).sum()
      15632 + df['er'] = df['change'] / (df['volatility'] + 0.0001)
      15633 + df['efficient'] = df['er'] > {threshold}
      15634 + df['direction'] = df['close'] > df['close'].shift({period})
      15635 + df['entry_signal'] = df['efficient'] & df['direction']""",
      15636 +         params={"period": [10], "threshold": [0.5, 0.6]},
      15637 +         direction="long",
      15638 +         lookback=20,
      15639 +         indicators=[],
      15640 +         combinable_with=["momentum", "volume"],
      15641 +         strategy_type="PEF",
      15642 +     ),
      15643 +     # Fractal Efficiency
      15644 +     PatternBlock(
      15645 +         id="FRACTAL_EFFICIENCY",
      15646 +         name="Fractal Efficiency",
      15647 +         category="price_efficiency",
      15648 +         formula_template="""df['range'] = df['high'].rolling({period}).max() - df['low'].rolling({period}).min()
      15649 + df['path'] = (df['high'] - df['low']).rolling({period}).sum()
      15650 + df['fe'] = df['range'] / (df['path'] + 0.0001)
      15651 + df['high_fe'] = df['fe'] > {threshold}
      15652 + df['trend_up'] = df['close'] > df['close'].shift({period})
      15653 + df['entry_signal'] = df['high_fe'] & df['trend_up']""",
      15654 +         params={"period": [10], "threshold": [0.4, 0.5]},
      15655 +         direction="long",
      15656 +         lookback=20,
      15657 +         indicators=[],
      15658 +         combinable_with=["volume", "confirmation"],
      15659 +         strategy_type="PEF",
      15660 +     ),
      15661 +     # Noise Filter
      15662 +     PatternBlock(
      15663 +         id="NOISE_FILTER",
      15664 +         name="Noise Filter",
      15665 +         category="price_efficiency",
      15666 +         formula_template="""df['signal'] = abs(df['close'] - df['close'].shift({period}))
      15667 + df['noise'] = df['close'].diff().abs().rolling({period}).sum()
      15668 + df['snr'] = df['signal'] / (df['noise'] + 0.0001)
      15669 + df['clean'] = df['snr'] > {threshold}
      15670 + df['bullish'] = df['close'] > df['close'].shift({period})
      15671 + df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
      15672 + df['entry_signal'] = df['clean'] & df['bullish'] & df['vol_confirm']""",
      15673 +         params={"period": [10], "threshold": [0.3, 0.4]},
      15674 +         direction="long",
      15675 +         lookback=25,
      15676 +         indicators=[],
      15677 +         combinable_with=["momentum", "threshold"],
      15678 +         strategy_type="PEF",
      15679 +     ),
      15680 + ]
      15681 +
      15682 +
      15683 + # =============================================================================
      15684 + # VOLUME CLIMAX EXTENDED BLOCKS
      15685 + # =============================================================================
      15686 +
      15687 + VOLUME_CLIMAX_EXT_BLOCKS = [
      15688 +     # Buying Climax
      15689 +     PatternBlock(
      15690 +         id="BUYING_CLIMAX",
      15691 +         name="Buying Climax",
      15692 +         category="volume_climax_ext",
      15693 +         formula_template="""df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
      15694 + df['wide_range'] = (df['high'] - df['low']) > (df['high'] - df['low']).rolling(20).mean() * 1.5
      15695 + df['close_high'] = df['close'] > (df['high'] + df['low']) / 2
      15696 + df['new_high'] = df['high'] >= df['high'].rolling(20).max()
      15697 + df['climax'] = df['vol_surge'] & df['wide_range'] & df['close_high'] & df['new_high']
      15698 + df['entry_signal'] = df['climax']""",
      15699 +         params={"mult": [2.0, 2.5]},
      15700 +         direction="long",
      15701 +         lookback=30,
      15702 +         indicators=[],
      15703 +         combinable_with=["momentum", "confirmation"],
      15704 +         strategy_type="VCX",
      15705 +     ),
      15706 +     # Selling Climax
      15707 +     PatternBlock(
      15708 +         id="SELLING_CLIMAX",
      15709 +         name="Selling Climax",
      15710 +         category="volume_climax_ext",
      15711 +         formula_template="""df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
      15712 + df['wide_range'] = (df['high'] - df['low']) > (df['high'] - df['low']).rolling(20).mean() * 1.5
      15713 + df['close_low'] = df['close'] < (df['high'] + df['low']) / 2
      15714 + df['new_low'] = df['low'] <= df['low'].rolling(20).min()
      15715 + df['climax'] = df['vol_surge'] & df['wide_range'] & df['close_low'] & df['new_low']
      15716 + df['reversal'] = df['close'] > df['open']
      15717 + df['entry_signal'] = df['climax'].shift(1) & df['reversal']""",
      15718 +         params={"mult": [2.0, 2.5]},
      15719 +         direction="long",
      15720 +         lookback=30,
      15721 +         indicators=[],
      15722 +         combinable_with=["volume", "threshold"],
      15723 +         strategy_type="VCX",
      15724 +     ),
      15725 +     # Exhaustion Volume
      15726 +     PatternBlock(
      15727 +         id="EXHAUSTION_VOL",
      15728 +         name="Exhaustion Volume",
      15729 +         category="volume_climax_ext",
      15730 +         formula_template="""df['vol_spike'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
      15731 + df['small_body'] = abs(df['close'] - df['open']) < (df['high'] - df['low']) * 0.3
      15732 + df['exhaustion'] = df['vol_spike'] & df['small_body']
      15733 + df['direction_change'] = (df['close'] > df['open']) != (df['close'].shift(1) > df['open'].shift(1))
      15734 + df['entry_signal'] = df['exhaustion'] & df['direction_change']""",
      15735 +         params={"mult": [2.0, 3.0]},
      15736 +         direction="bidi",
      15737 +         lookback=25,
      15738 +         indicators=[],
      15739 +         combinable_with=["momentum", "confirmation"],
      15740 +         strategy_type="VCX",
      15741 +     ),
      15742 + ]
      15743 +
      15744 +
      15745 + # =============================================================================
      15746 + # REVERSAL CONFIRM BLOCKS
      15747 + # =============================================================================
      15748 +
      15749 + REVERSAL_CONFIRM_BLOCKS = [
      15750 +     # Pin Bar Confirm
      15751 +     PatternBlock(
      15752 +         id="PIN_BAR_CONFIRM",
      15753 +         name="Pin Bar Confirm",
      15754 +         category="reversal_confirm",
      15755 +         formula_template="""df['body'] = abs(df['close'] - df['open'])
      15756 + df['range'] = df['high'] - df['low']
      15757 + df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
      15758 + df['pin_bar'] = (df['lower_wick'] > df['body'] * {mult}) & (df['body'] < df['range'] * 0.3)
      15759 + df['at_low'] = df['low'] <= df['low'].rolling(10).min() * 1.01
      15760 + df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean()
      15761 + df['entry_signal'] = df['pin_bar'] & df['at_low'] & df['vol_confirm']""",
      15762 +         params={"mult": [2.0, 2.5]},
      15763 +         direction="long",
      15764 +         lookback=20,
      15765 +         indicators=[],
      15766 +         combinable_with=["volume", "momentum"],
      15767 +         strategy_type="RVC",
      15768 +     ),
      15769 +     # Engulfing Confirm
      15770 +     PatternBlock(
      15771 +         id="ENGULFING_CONFIRM",
      15772 +         name="Engulfing Confirm",
      15773 +         category="reversal_confirm",
      15774 +         formula_template="""df['prev_bearish'] = df['close'].shift(1) < df['open'].shift(1)
      15775 + df['curr_bullish'] = df['close'] > df['open']
      15776 + df['engulfs'] = (df['open'] < df['close'].shift(1)) & (df['close'] > df['open'].shift(1))
      15777 + df['engulfing'] = df['prev_bearish'] & df['curr_bullish'] & df['engulfs']
      15778 + df['at_support'] = df['low'] <= df['low'].rolling(10).min() * 1.02
      15779 + df['entry_signal'] = df['engulfing'] & df['at_support']""",
      15780 +         params={},
      15781 +         direction="long",
      15782 +         lookback=20,
      15783 +         indicators=[],
      15784 +         combinable_with=["volume", "confirmation"],
      15785 +         strategy_type="RVC",
      15786 +     ),
      15787 +     # Key Reversal
      15788 +     PatternBlock(
      15789 +         id="KEY_REVERSAL",
      15790 +         name="Key Reversal",
      15791 +         category="reversal_confirm",
      15792 +         formula_template="""df['new_low'] = df['low'] < df['low'].shift(1).rolling(5).min()
      15793 + df['close_above'] = df['close'] > df['high'].shift(1)
      15794 + df['key_rev'] = df['new_low'] & df['close_above']
      15795 + df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * {mult}
      15796 + df['entry_signal'] = df['key_rev'] & df['vol_surge']""",
      15797 +         params={"mult": [1.5, 2.0]},
      15798 +         direction="long",
      15799 +         lookback=15,
      15800 +         indicators=[],
      15801 +         combinable_with=["momentum", "threshold"],
      15802 +         strategy_type="RVC",
      15803 +     ),
      15804 + ]
      15805 +
      15806 +
      15807 + # =============================================================================
      15808 + # CONTINUATION PATTERN BLOCKS
      15809 + # =============================================================================
      15810 +
      15811 + CONTINUATION_PATTERN_BLOCKS = [
      15812 +     # Flag Breakout
      15813 +     PatternBlock(
      15814 +         id="FLAG_BREAKOUT",
      15815 +         name="Flag Breakout",
      15816 +         category="continuation_pattern",
      15817 +         formula_template="""df['prior_move'] = df['close'].shift(5) - df['close'].shift(15)
      15818 + df['strong_move'] = df['prior_move'] > df['close'].shift(15) * 0.05
      15819 + df['consolidation'] = (df['high'].rolling(5).max() - df['low'].rolling(5).min()) < df['close'] * 0.02
      15820 + df['breakout'] = df['close'] > df['high'].shift(1).rolling(5).max()
      15821 + df['entry_signal'] = df['strong_move'] & df['consolidation'].shift(1) & df['breakout']""",
      15822 +         params={},
      15823 +         direction="long",
      15824 +         lookback=25,
      15825 +         indicators=[],
      15826 +         combinable_with=["volume", "momentum"],
      15827 +         strategy_type="CNP",
      15828 +     ),
      15829 +     # Pennant Break
      15830 +     PatternBlock(
      15831 +         id="PENNANT_BREAK",
      15832 +         name="Pennant Break",
      15833 +         category="continuation_pattern",
      15834 +         formula_template="""df['range'] = df['high'].rolling(5).max() - df['low'].rolling(5).min()
      15835 + df['range_shrink'] = df['range'] < df['range'].shift(5) * {mult}
      15836 + df['shrink_days'] = df['range_shrink'].rolling(5).sum() >= 3
      15837 + df['break_up'] = df['close'] > df['high'].shift(1).rolling(3).max()
      15838 + df['vol_up'] = df['volume'] > df['volume'].shift(1)
      15839 + df['entry_signal'] = df['shrink_days'].shift(1) & df['break_up'] & df['vol_up']""",
      15840 +         params={"mult": [0.7, 0.8]},
      15841 +         direction="long",
      15842 +         lookback=20,
      15843 +         indicators=[],
      15844 +         combinable_with=["momentum", "confirmation"],
      15845 +         strategy_type="CNP",
      15846 +     ),
      15847 +     # Triangle Break
      15848 +     PatternBlock(
      15849 +         id="TRIANGLE_BREAK",
      15850 +         name="Triangle Break",
      15851 +         category="continuation_pattern",
      15852 +         formula_template="""df['high_slope'] = df['high'].rolling({period}).apply(lambda x: (x.iloc[-1] - x.iloc[0]) / {period},
            +raw=False)
      15853 + df['low_slope'] = df['low'].rolling({period}).apply(lambda x: (x.iloc[-1] - x.iloc[0]) / {period}, raw=False)
      15854 + df['converging'] = (df['high_slope'] < 0) & (df['low_slope'] > 0)
      15855 + df['break_high'] = df['close'] > df['high'].shift(1).rolling(5).max()
      15856 + df['vol_confirm'] = df['volume'] > df['volume'].rolling(20).mean() * 1.3
      15857 + df['entry_signal'] = df['converging'].shift(1) & df['break_high'] & df['vol_confirm']""",
      15858 +         params={"period": [10]},
      15859 +         direction="long",
      15860 +         lookback=20,
      15861 +         indicators=[],
      15862 +         combinable_with=["volume", "threshold"],
      15863 +         strategy_type="CNP",
      15864 +     ),
      15865 + ]
      15866 +
      15867 +
      15868 + # =============================================================================
      15869 + # OSCILLATOR CROSS EXTENDED BLOCKS
      15870 + # =============================================================================
      15871 +
      15872 + OSCILLATOR_CROSS_EXT_BLOCKS = [
      15873 +     # RSI Cross 50
      15874 +     PatternBlock(
      15875 +         id="RSI_CROSS_50",
      15876 +         name="RSI Cross 50",
      15877 +         category="oscillator_cross_ext",
      15878 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod={period})
      15879 + df['cross_up'] = (df['rsi'] > 50) & (df['rsi'].shift(1) <= 50)
      15880 + df['momentum'] = df['rsi'] > df['rsi'].shift(3)
      15881 + df['entry_signal'] = df['cross_up'] & df['momentum']""",
      15882 +         params={"period": [14]},
      15883 +         direction="long",
      15884 +         lookback=25,
      15885 +         indicators=["RSI"],
      15886 +         combinable_with=["volume", "confirmation"],
      15887 +         strategy_type="OCX",
      15888 +     ),
      15889 +     # Stoch Cross
      15890 +     PatternBlock(
      15891 +         id="STOCH_CROSS_EXT",
      15892 +         name="Stoch Cross Extended",
      15893 +         category="oscillator_cross_ext",
      15894 +         formula_template="""df['stoch_k'], df['stoch_d'] = ta.STOCH(df['high'], df['low'], df['close'], fastk_period=14,
            +slowk_period=3, slowd_period=3)
      15895 + df['cross_up'] = (df['stoch_k'] > df['stoch_d']) & (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1))
      15896 + df['oversold_zone'] = df['stoch_k'] < {level}
      15897 + df['entry_signal'] = df['cross_up'] & df['oversold_zone']""",
      15898 +         params={"level": [30, 40]},
      15899 +         direction="long",
      15900 +         lookback=25,
      15901 +         indicators=["STOCH"],
      15902 +         combinable_with=["momentum", "threshold"],
      15903 +         strategy_type="OCX",
      15904 +     ),
      15905 +     # CCI Zero Cross
      15906 +     PatternBlock(
      15907 +         id="CCI_ZERO_CROSS",
      15908 +         name="CCI Zero Cross",
      15909 +         category="oscillator_cross_ext",
      15910 +         formula_template="""df['cci'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod={period})
      15911 + df['cross_up'] = (df['cci'] > 0) & (df['cci'].shift(1) <= 0)
      15912 + df['was_oversold'] = df['cci'].shift(3) < -50
      15913 + df['entry_signal'] = df['cross_up'] & df['was_oversold']""",
      15914 +         params={"period": [14, 20]},
      15915 +         direction="long",
      15916 +         lookback=30,
      15917 +         indicators=["CCI"],
      15918 +         combinable_with=["volume", "confirmation"],
      15919 +         strategy_type="OCX",
      15920 +     ),
      15921 + ]
      15922 +
      15923 +
      15924 + # =============================================================================
      15925 + # MA SYSTEM BLOCKS (MAS2)
      15926 + # =============================================================================
      15927 +
      15928 + MA_SYSTEM_EXT_BLOCKS = [
      15929 +     # Triple MA System
      15930 +     PatternBlock(
      15931 +         id="TRIPLE_MA_SYS",
      15932 +         name="Triple MA System",
      15933 +         category="ma_system_ext",
      15934 +         formula_template="""df['ema_fast'] = ta.EMA(df['close'], timeperiod={fast})
      15935 + df['ema_med'] = ta.EMA(df['close'], timeperiod={med})
      15936 + df['ema_slow'] = ta.EMA(df['close'], timeperiod={slow})
      15937 + df['aligned'] = (df['ema_fast'] > df['ema_med']) & (df['ema_med'] > df['ema_slow'])
      15938 + df['pullback'] = df['low'] <= df['ema_fast'] * 1.01
      15939 + df['bounce'] = df['close'] > df['ema_fast']
      15940 + df['entry_signal'] = df['aligned'] & df['pullback'] & df['bounce']""",
      15941 +         params={"fast": [10], "med": [20], "slow": [50]},
      15942 +         direction="long",
      15943 +         lookback=60,
      15944 +         indicators=["EMA"],
      15945 +         combinable_with=["volume", "momentum"],
      15946 +         strategy_type="MAS",
      15947 +     ),
      15948 +     # Ribbon Expansion
      15949 +     PatternBlock(
      15950 +         id="RIBBON_EXPANSION",
      15951 +         name="Ribbon Expansion",
      15952 +         category="ma_system_ext",
      15953 +         formula_template="""df['ema10'] = ta.EMA(df['close'], timeperiod=10)
      15954 + df['ema20'] = ta.EMA(df['close'], timeperiod=20)
      15955 + df['ema30'] = ta.EMA(df['close'], timeperiod=30)
      15956 + df['spread'] = (df['ema10'] - df['ema30']) / df['close'] * 100
      15957 + df['expanding'] = df['spread'] > df['spread'].shift(3)
      15958 + df['positive'] = df['spread'] > 0
      15959 + df['entry_signal'] = df['expanding'] & df['positive']""",
      15960 +         params={},
      15961 +         direction="long",
      15962 +         lookback=40,
      15963 +         indicators=["EMA"],
      15964 +         combinable_with=["momentum", "confirmation"],
      15965 +         strategy_type="MAS",
      15966 +     ),
      15967 +     # MA Squeeze
      15968 +     PatternBlock(
      15969 +         id="MA_SQUEEZE",
      15970 +         name="MA Squeeze",
      15971 +         category="ma_system_ext",
      15972 +         formula_template="""df['ema10'] = ta.EMA(df['close'], timeperiod=10)
      15973 + df['ema20'] = ta.EMA(df['close'], timeperiod=20)
      15974 + df['ema50'] = ta.EMA(df['close'], timeperiod=50)
      15975 + df['spread'] = (df['ema10'] - df['ema50']).abs() / df['close'] * 100
      15976 + df['tight'] = df['spread'] < {threshold}
      15977 + df['break_up'] = df['close'] > df['ema10']
      15978 + df['vol_surge'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
      15979 + df['entry_signal'] = df['tight'].shift(1) & df['break_up'] & df['vol_surge']""",
      15980 +         params={"threshold": [1.0, 1.5]},
      15981 +         direction="long",
      15982 +         lookback=60,
      15983 +         indicators=["EMA"],
      15984 +         combinable_with=["volume", "threshold"],
      15985 +         strategy_type="MAS",
      15986 +     ),
      15987 + ]
      15988 +
      15989 +
      15990 + # =============================================================================
      15991 + # PRICE LEVEL BLOCKS
      15992 + # =============================================================================
      15993 +
      15994 + PRICE_LEVEL_BLOCKS = [
      15995 +     # Round Number
      15996 +     PatternBlock(
      15997 +         id="ROUND_NUMBER",
      15998 +         name="Round Number",
      15999 +         category="price_level",
      16000 +         formula_template="""df['round_level'] = (df['close'] / {increment}).round() * {increment}
      16001 + df['near_round'] = abs(df['close'] - df['round_level']) / df['close'] < 0.005
      16002 + df['bounce'] = (df['low'] <= df['round_level'] * 1.005) & (df['close'] > df['round_level'])
      16003 + df['bullish'] = df['close'] > df['open']
      16004 + df['entry_signal'] = df['near_round'] & df['bounce'] & df['bullish']""",
      16005 +         params={"increment": [100, 1000]},
      16006 +         direction="long",
      16007 +         lookback=10,
      16008 +         indicators=[],
      16009 +         combinable_with=["volume", "confirmation"],
      16010 +         strategy_type="PLV",
      16011 +     ),
      16012 +     # Psychological Level
      16013 +     PatternBlock(
      16014 +         id="PSYCH_LEVEL",
      16015 +         name="Psychological Level",
      16016 +         category="price_level",
      16017 +         formula_template="""df['pct_level'] = df['close'].rolling(50).min() * {mult}
      16018 + df['near_level'] = abs(df['close'] - df['pct_level']) / df['close'] < 0.01
      16019 + df['support_test'] = df['low'] <= df['pct_level'] * 1.01
      16020 + df['hold'] = df['close'] > df['pct_level']
      16021 + df['entry_signal'] = df['near_level'] & df['support_test'] & df['hold']""",
      16022 +         params={"mult": [1.1, 1.2]},
      16023 +         direction="long",
      16024 +         lookback=60,
      16025 +         indicators=[],
      16026 +         combinable_with=["momentum", "threshold"],
      16027 +         strategy_type="PLV",
      16028 +     ),
      16029 +     # Pivot Cluster
      16030 +     PatternBlock(
      16031 +         id="PIVOT_CLUSTER",
      16032 +         name="Pivot Cluster",
      16033 +         category="price_level",
      16034 +         formula_template="""df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
      16035 + df['s1'] = 2 * df['pivot'] - df['high'].shift(1)
      16036 + df['near_pivot'] = abs(df['close'] - df['pivot']) / df['close'] < 0.005
      16037 + df['near_s1'] = abs(df['close'] - df['s1']) / df['close'] < 0.01
      16038 + df['at_support'] = df['near_pivot'] | df['near_s1']
      16039 + df['bounce'] = df['close'] > df['open']
      16040 + df['entry_signal'] = df['at_support'] & df['bounce']""",
      16041 +         params={},
      16042 +         direction="long",
      16043 +         lookback=10,
      16044 +         indicators=[],
      16045 +         combinable_with=["volume", "momentum"],
      16046 +         strategy_type="PLV",
      16047 +     ),
      16048 + ]
      16049 +
      16050 +
      16051 + # =============================================================================
      16052 + # VOLATILITY SQUEEZE EXTENDED BLOCKS
      16053 + # =============================================================================
      16054 +
      16055 + VOLATILITY_SQUEEZE_EXT_BLOCKS = [
      16056 +     # Keltner Squeeze
      16057 +     PatternBlock(
      16058 +         id="KELTNER_SQUEEZE",
      16059 +         name="Keltner Squeeze",
      16060 +         category="volatility_squeeze_ext",
      16061 +         formula_template="""df['ema'] = ta.EMA(df['close'], timeperiod=20)
      16062 + df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
      16063 + df['kc_upper'] = df['ema'] + df['atr'] * 1.5
      16064 + df['kc_lower'] = df['ema'] - df['atr'] * 1.5
      16065 + df['bb_upper'], _, df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
      16066 + df['squeeze'] = (df['bb_lower'] > df['kc_lower']) & (df['bb_upper'] < df['kc_upper'])
      16067 + df['release'] = df['squeeze'].shift(1) & ~df['squeeze']
      16068 + df['bullish'] = df['close'] > df['ema']
      16069 + df['entry_signal'] = df['release'] & df['bullish']""",
      16070 +         params={},
      16071 +         direction="long",
      16072 +         lookback=35,
      16073 +         indicators=["EMA", "ATR", "BBANDS"],
      16074 +         combinable_with=["momentum", "volume"],
      16075 +         strategy_type="VSQ",
      16076 +     ),
      16077 +     # BB Squeeze Signal
      16078 +     PatternBlock(
      16079 +         id="BB_SQUEEZE_SIG",
      16080 +         name="BB Squeeze Signal",
      16081 +         category="volatility_squeeze_ext",
      16082 +         formula_template="""df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2,
            +nbdevdn=2)
      16083 + df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
      16084 + df['width_pct'] = df['bb_width'].rolling(50).apply(lambda x: (x.iloc[-1] < x).sum() / len(x) * 100, raw=False)
      16085 + df['extreme_squeeze'] = df['width_pct'] < {threshold}
      16086 + df['break_up'] = df['close'] > df['bb_upper']
      16087 + df['entry_signal'] = df['extreme_squeeze'].shift(1) & df['break_up']""",
      16088 +         params={"threshold": [10, 15]},
      16089 +         direction="long",
      16090 +         lookback=60,
      16091 +         indicators=["BBANDS"],
      16092 +         combinable_with=["volume", "confirmation"],
      16093 +         strategy_type="VSQ",
      16094 +     ),
      16095 +     # ATR Squeeze
      16096 +     PatternBlock(
      16097 +         id="ATR_SQUEEZE",
      16098 +         name="ATR Squeeze",
      16099 +         category="volatility_squeeze_ext",
      16100 +         formula_template="""df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
      16101 + df['atr_ma'] = df['atr'].rolling(20).mean()
      16102 + df['squeeze'] = df['atr'] < df['atr_ma'] * {mult}
      16103 + df['squeeze_days'] = df['squeeze'].rolling(5).sum() >= 3
      16104 + df['expansion'] = df['atr'] > df['atr'].shift(1)
      16105 + df['direction'] = df['close'] > df['close'].shift(3)
      16106 + df['entry_signal'] = df['squeeze_days'].shift(1) & df['expansion'] & df['direction']""",
      16107 +         params={"mult": [0.7, 0.8]},
      16108 +         direction="long",
      16109 +         lookback=35,
      16110 +         indicators=["ATR"],
      16111 +         combinable_with=["momentum", "threshold"],
      16112 +         strategy_type="VSQ",
      16113 +     ),
      16114 + ]
      16115 +
      16116 +
      16117 + # =============================================================================
      16118 + # SENTIMENT PROXY BLOCKS
      16119 + # =============================================================================
      16120 +
      16121 + SENTIMENT_PROXY_BLOCKS = [
      16122 +     # Fear Extreme
      16123 +     PatternBlock(
      16124 +         id="FEAR_EXTREME",
      16125 +         name="Fear Extreme",
      16126 +         category="sentiment_proxy",
      16127 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      16128 + df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
      16129 + df['below_bb'] = df['close'] < df['bb_lower']
      16130 + df['rsi_fear'] = df['rsi'] < {rsi_level}
      16131 + df['vol_spike'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
      16132 + df['fear'] = df['below_bb'] & df['rsi_fear'] & df['vol_spike']
      16133 + df['entry_signal'] = df['fear']""",
      16134 +         params={"rsi_level": [25, 30]},
      16135 +         direction="long",
      16136 +         lookback=30,
      16137 +         indicators=["RSI", "BBANDS"],
      16138 +         combinable_with=["volume", "confirmation"],
      16139 +         strategy_type="SNT",
      16140 +     ),
      16141 +     # Greed Extreme
      16142 +     PatternBlock(
      16143 +         id="GREED_EXTREME",
      16144 +         name="Greed Extreme",
      16145 +         category="sentiment_proxy",
      16146 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      16147 + df['bb_upper'], df['bb_mid'], df['bb_lower'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
      16148 + df['above_bb'] = df['close'] > df['bb_upper']
      16149 + df['rsi_greed'] = df['rsi'] > {rsi_level}
      16150 + df['vol_spike'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
      16151 + df['greed'] = df['above_bb'] & df['rsi_greed'] & df['vol_spike']
      16152 + df['entry_signal'] = df['greed']""",
      16153 +         params={"rsi_level": [70, 75]},
      16154 +         direction="short",
      16155 +         lookback=30,
      16156 +         indicators=["RSI", "BBANDS"],
      16157 +         combinable_with=["volume", "momentum"],
      16158 +         strategy_type="SNT",
      16159 +     ),
      16160 +     # Sentiment Flip
      16161 +     PatternBlock(
      16162 +         id="SENTIMENT_FLIP",
      16163 +         name="Sentiment Flip",
      16164 +         category="sentiment_proxy",
      16165 +         formula_template="""df['rsi'] = ta.RSI(df['close'], timeperiod=14)
      16166 + df['was_fear'] = df['rsi'].shift(5) < 30
      16167 + df['now_neutral'] = df['rsi'] > 45
      16168 + df['price_recover'] = df['close'] > df['close'].shift(5)
      16169 + df['flip'] = df['was_fear'] & df['now_neutral'] & df['price_recover']
      16170 + df['entry_signal'] = df['flip']""",
      16171 +         params={},
      16172 +         direction="long",
      16173 +         lookback=25,
      16174 +         indicators=["RSI"],
      16175 +         combinable_with=["volume", "threshold"],
      16176 +         strategy_type="SNT",
      16177 +     ),
      16178 + ]
      16179 +
      16180 +
      16181 + # =============================================================================
      16182   # ALL BLOCKS COMBINED
      16183   # =============================================================================
      16184

● Search(pattern: "EXIT_SIGNAL_BLOCKS$", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 25 lines

● Update(src/generator/pattern_gen/building_blocks.py)
  ⎿  Added 10 lines
      16407       + TREND_FILTER_BLOCKS
      16408       + ENTRY_TIMING_BLOCKS
      16409       + EXIT_SIGNAL_BLOCKS
      16410 +     + MARKET_REGIME_BLOCKS
      16411 +     + PRICE_EFFICIENCY_BLOCKS
      16412 +     + VOLUME_CLIMAX_EXT_BLOCKS
      16413 +     + REVERSAL_CONFIRM_BLOCKS
      16414 +     + CONTINUATION_PATTERN_BLOCKS
      16415 +     + OSCILLATOR_CROSS_EXT_BLOCKS
      16416 +     + MA_SYSTEM_EXT_BLOCKS
      16417 +     + PRICE_LEVEL_BLOCKS
      16418 +     + VOLATILITY_SQUEEZE_EXT_BLOCKS
      16419 +     + SENTIMENT_PROXY_BLOCKS
      16420   )
      16421
      16422   # Index by ID for quick lookup

● Bash(source .venv/bin/activate && python3 << 'EOF'
      import sys…)
  ⎿  Total blocks: 808
     Categories: 233
     … +37 lines (ctrl+o to expand)

● Round 23 completato!

  Risultati:
  - Blocchi totali: 808 (+30 nuovi)
  - Categorie: 233
  - Tipi strategia: 220
  - Validazione: 200/200 strategie valide
  - Lookahead: Nessun pattern rilevato
  - Strategie stimate: ~152,960

  Nuovi blocchi aggiunti (Round 23):
  1. MARKET_REGIME_BLOCKS (MRG): Trending/ranging/volatile regime
  2. PRICE_EFFICIENCY_BLOCKS (PEF): Efficiency ratio/fractal efficiency/noise filter
  3. VOLUME_CLIMAX_EXT_BLOCKS (VCX): Buying/selling climax/exhaustion volume
  4. REVERSAL_CONFIRM_BLOCKS (RVC): Pin bar/engulfing/key reversal confirm
  5. CONTINUATION_PATTERN_BLOCKS (CNP): Flag/pennant/triangle breakout
  6. OSCILLATOR_CROSS_EXT_BLOCKS (OCX): RSI cross 50/Stoch cross/CCI zero
  7. MA_SYSTEM_EXT_BLOCKS (MAS): Triple MA/ribbon expansion/MA squeeze
  8. PRICE_LEVEL_BLOCKS (PLV): Round number/psychological/pivot cluster
  9. VOLATILITY_SQUEEZE_EXT_BLOCKS (VSQ): Keltner/BB squeeze/ATR squeeze
  10. SENTIMENT_PROXY_BLOCKS (SNT): Fear/greed extreme/sentiment flip

  Progressione sessione:
  ┌───────┬─────────┬───────────────────┐
  │ Round │ Blocchi │ Strategie stimate │
  ├───────┼─────────┼───────────────────┤
  │ 21    │ 748     │ ~144,368          │
  ├───────┼─────────┼───────────────────┤
  │ 22    │ 778     │ ~148,680          │
  ├───────┼─────────┼───────────────────┤
  │ 23    │ 808     │ ~152,960          │
  └───────┴─────────┴───────────────────┘
  Hai testato che tutto funzioni? Altre possibili migliorie? (stessi requisiti)

✻ Brewed for 2m 51s

❯ hai testato che tutto funzioni?
  altre possibili migliorie? con gli stessi requisiti, cioè no modifiche al codice esistente, piena compatibilità, no diminuzione strategie
  dimmi solo

● Test Round 23: PASSATO
  - 200/200 strategie valide
  - 0 errori lookahead
  - 808 blocchi funzionanti

  ---
  Proposta Round 24 - 10 nuove categorie (30 blocchi):

  1. DIVERGENCE_MULTI_BLOCKS (DVX): RSI+MACD divergence, triple osc divergence, volume divergence
  2. BREAKOUT_FILTER_BLOCKS (BKF): Volume breakout filter, ATR breakout filter, momentum breakout filter
  3. MEAN_REVERSION_EXT_BLOCKS (MRV): Bollinger mean reversion, RSI mean reversion, Z-score reversion
  4. TREND_STRENGTH_EXT_BLOCKS (TSE): ADX strength, slope strength, momentum strength
  5. CANDLE_SEQUENCE_BLOCKS (CSQ): Three white soldiers, three black crows, morning star
  6. VOLATILITY_FILTER_BLOCKS (VFL): High vol filter, low vol filter, vol regime filter
  7. PRICE_PATTERN_EXT_BLOCKS (PPE): Cup handle, ascending triangle, descending triangle
  8. MOMENTUM_FILTER_EXT_BLOCKS (MFE): RSI filter, MACD filter, Stoch filter
  9. VOLUME_ANALYSIS_EXT_BLOCKS (VAX): Volume trend, volume breakout, volume reversal
  10. CROSS_INDICATOR_BLOCKS (CRI): MA+RSI combo, BB+Volume combo, ADX+DI combo

  Risultato atteso:
  - Blocchi: 808 → 838 (+30)
  - Strategie: ~152,960 → ~157,300+

  Vuoi procedere?

❯ si

● Search(pattern: "^SENTIMENT_PROXY_BLOCKS = \[", path: "src/generator/pattern_gen/building_blocks.py", output_mode: "content")
  ⎿  Found 1 line (ctrl+o to expand)

● Read(src/generator/pattern_gen/building_blocks.py)
  ⎿  Read 50 lines

✶ Adding DIVERGENCE_MULTI_BLOCKS… (ctrl+c to interrupt · ctrl+t to hide todos · thinking)
  ⎿  ☐ Add DIVERGENCE_MULTI_BLOCKS
     ☐ Add BREAKOUT_FILTER_BLOCKS
     ☐ Add MEAN_REVERSION_EXT_BLOCKS
     ☐ Add TREND_STRENGTH_EXT_BLOCKS
     ☐ Add CANDLE_SEQUENCE_BLOCKS
     ☐ Add VOLATILITY_FILTER_BLOCKS
     ☐ Add PRICE_PATTERN_EXT_BLOCKS
     ☐ Add MOMENTUM_FILTER_EXT_BLOCKS
     ☐ Add VOLUME_ANALYSIS_EXT_BLOCKS
     ☐ Add CROSS_INDICATOR_BLOCKS
     ☐ Update ALL_BLOCKS and validate