//+------------------------------------------------------------------+
//| QuantEA.mq5 — Expert Advisor orchestrateur (volontairement fin). |
//| Toute la logique vit dans les modules mql5/libraries/*.mqh :     |
//| Logger, SignalReceiver, RiskManager, TradeManager.               |
//| L'EA se contente de câbler les modules et de piloter le cycle.   |
//+------------------------------------------------------------------+
#property strict

#include "../libraries/Logger.mqh"
#include "../libraries/SignalReceiver.mqh"
#include "../libraries/RiskManager.mqh"
#include "../libraries/TradeManager.mqh"

//--- Paramètres (tous configurables) ---------------------------------
input string InpSymbols          = "EURUSD,GBPUSD,USDJPY"; // multi-symboles
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M15;           // timeframe de gestion
input string InpHost             = "127.0.0.1";
input int    InpPort             = 5555;
input int    InpSignalTTL        = 30;
input ulong  InpMagic            = 990011;
//--- Risque
input double InpRiskPerTrade     = 0.01;
input double InpMaxDailyLoss     = 0.02;
input double InpMaxDrawdown      = 0.10;
input double InpMaxSpread        = 30;
input int    InpMaxPositions     = 5;
//--- Stops (en multiples d'ATR)
input double InpAtrSL            = 1.5;
input double InpAtrTP            = 3.0;
input double InpTrailingAtr      = 1.0;
input double InpBreakevenAtr     = 1.0;
input bool   InpAutoShutdown     = true;

//--- Instances de modules --------------------------------------------
CLogger         g_log;
CSignalReceiver g_receiver;
CRiskManager    g_risk;
CTradeManager   g_trade;
string          g_symbols[];
int             g_atr_handles[];
datetime        g_last_day=0;

//+------------------------------------------------------------------+
int OnInit()
  {
   g_log.Init(LOG_INFO,"QuantEA.log");

   int n=StringSplit(InpSymbols,',',g_symbols);
   if(n<=0){ g_log.Log(LOG_ERROR,"Aucun symbole configuré"); return INIT_FAILED; }
   ArrayResize(g_atr_handles,n);
   for(int i=0;i<n;i++)
     {
      StringTrimLeft(g_symbols[i]); StringTrimRight(g_symbols[i]);
      g_atr_handles[i]=iATR(g_symbols[i],InpTimeframe,14);
      if(g_atr_handles[i]==INVALID_HANDLE)
        { g_log.Log(LOG_ERROR,"iATR indisponible: "+g_symbols[i]); return INIT_FAILED; }
     }

   RiskConfig rc;
   rc.risk_per_trade_pct=InpRiskPerTrade; rc.max_daily_loss_pct=InpMaxDailyLoss;
   rc.max_drawdown_pct=InpMaxDrawdown;    rc.max_spread_points=InpMaxSpread;
   rc.max_open_positions=InpMaxPositions; rc.atr_sl_mult=InpAtrSL;
   rc.atr_tp_mult=InpAtrTP;               rc.auto_shutdown=InpAutoShutdown;
   g_risk.Init(rc,&g_log);

   StopConfig sc;
   sc.atr_sl_mult=InpAtrSL; sc.atr_tp_mult=InpAtrTP;
   sc.trailing_atr_mult=InpTrailingAtr; sc.breakeven_atr_mult=InpBreakevenAtr;
   g_trade.Init(InpMagic,sc,&g_log);

   if(!g_receiver.Init(InpHost,InpPort,InpSignalTTL,&g_log))
      return INIT_FAILED;

   g_log.Log(LOG_INFO,"QuantEA initialisé");
   return INIT_SUCCEEDED;
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   g_receiver.Deinit();
   for(int i=0;i<ArraySize(g_atr_handles);i++) IndicatorRelease(g_atr_handles[i]);
   g_log.Deinit();
  }
//+------------------------------------------------------------------+
double CurrentAtr(int idx)
  {
   double buf[]; if(CopyBuffer(g_atr_handles[idx],0,0,1,buf)<=0) return 0.0;
   return buf[0];
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   // Réinitialisation quotidienne des compteurs de risque.
   MqlDateTime dt; TimeToStruct(TimeCurrent(),dt);
   datetime today=StringToTime(StringFormat("%04d.%02d.%02d",dt.year,dt.mon,dt.day));
   if(today!=g_last_day){ g_risk.OnNewDay(); g_last_day=today; }

   if(g_risk.CircuitBreakerTriggered()) return;  // trading gelé si coupe-circuit

   // Gestion des positions ouvertes (trailing / break even) par symbole.
   for(int i=0;i<ArraySize(g_symbols);i++)
      g_trade.ManageOpenPositions(CurrentAtr(i));

   // Réception d'un signal et exécution éventuelle.
   Signal s=g_receiver.Poll();
   if(!s.valid || s.side==0) return;

   int idx=-1;
   for(int i=0;i<ArraySize(g_symbols);i++) if(g_symbols[i]==s.symbol){ idx=i; break; }
   if(idx<0){ g_log.Log(LOG_WARN,"Signal pour symbole non géré: "+s.symbol); return; }

   int open=g_trade.CountPositions();
   if(!g_risk.AllowTrade(s.symbol,open)) return;

   double atr=(s.atr>0)?s.atr:CurrentAtr(idx);
   double lots=g_risk.LotSize(s.symbol,atr);
   g_trade.Open(s.symbol,s.side,lots,atr);
  }
//+------------------------------------------------------------------+
