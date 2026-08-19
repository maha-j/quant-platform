//+------------------------------------------------------------------+
//| RiskManager.mqh — garde-fous côté terminal.                      |
//| Responsabilité unique : autoriser/refuser un trade et dimension- |
//| ner le lot. Toutes les bornes sont des paramètres configurables. |
//| (Miroir léger du moteur institutionnel Python — dernière ligne   |
//| de défense locale.)                                              |
//+------------------------------------------------------------------+
#ifndef QUANT_RISK_MANAGER_MQH
#define QUANT_RISK_MANAGER_MQH

#include "Logger.mqh"

struct RiskConfig
  {
   double risk_per_trade_pct;   // 0.01 = 1 %
   double max_daily_loss_pct;   // 0.02 = 2 %
   double max_drawdown_pct;     // 0.10 = 10 %
   double max_spread_points;
   int    max_open_positions;
   double atr_sl_mult;
   double atr_tp_mult;
   bool   auto_shutdown;
  };

class CRiskManager
  {
private:
   RiskConfig m_cfg;
   double     m_day_start_equity;
   double     m_peak_equity;
   bool       m_halted;
   CLogger   *m_log;
public:
   void Init(const RiskConfig &cfg,CLogger *log)
     {
      m_cfg=cfg; m_log=log; m_halted=false;
      m_day_start_equity=AccountInfoDouble(ACCOUNT_EQUITY);
      m_peak_equity=m_day_start_equity;
     }
   void OnNewDay() { m_day_start_equity=AccountInfoDouble(ACCOUNT_EQUITY); }

   // Coupe-circuits globaux. Retourne true si le trading doit être stoppé.
   bool CircuitBreakerTriggered()
     {
      double eq=AccountInfoDouble(ACCOUNT_EQUITY);
      if(eq>m_peak_equity) m_peak_equity=eq;
      double daily_dd=1.0-eq/m_day_start_equity;
      double peak_dd =1.0-eq/m_peak_equity;
      if(daily_dd>=m_cfg.max_daily_loss_pct)
        { m_log.Log(LOG_ERROR,StringFormat("Max daily loss %.2f%%",daily_dd*100)); m_halted=m_cfg.auto_shutdown; return true; }
      if(peak_dd>=m_cfg.max_drawdown_pct)
        { m_log.Log(LOG_ERROR,StringFormat("Max drawdown %.2f%%",peak_dd*100)); m_halted=m_cfg.auto_shutdown; return true; }
      return false;
     }
   bool IsHalted() const { return m_halted; }

   // Filtres pré-trade locaux.
   bool AllowTrade(const string symbol,int open_positions)
     {
      if(m_halted) return false;
      if(open_positions>=m_cfg.max_open_positions){ m_log.Log(LOG_WARN,"Max positions atteint"); return false; }
      double spread=(double)SymbolInfoInteger(symbol,SYMBOL_SPREAD);
      if(spread>m_cfg.max_spread_points){ m_log.Log(LOG_WARN,"Spread trop élevé: "+symbol); return false; }
      return true;
     }

   // Position sizing par risque fixe basé sur la distance de stop (ATR).
   double LotSize(const string symbol,double atr)
     {
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      double risk_amount=equity*m_cfg.risk_per_trade_pct;
      double sl_distance=atr*m_cfg.atr_sl_mult;
      double tick_value=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_VALUE);
      double tick_size =SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
      if(sl_distance<=0 || tick_value<=0 || tick_size<=0) return 0.0;
      double value_per_price=tick_value/tick_size;
      double lots=risk_amount/(sl_distance*value_per_price);
      double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
      double minv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
      double maxv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
      lots=MathFloor(lots/step)*step;
      return MathMax(minv,MathMin(maxv,lots));
     }
  };
#endif
