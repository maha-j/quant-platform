//+------------------------------------------------------------------+
//| TradeManager.mqh — exécution des ordres et gestion des stops.    |
//| Responsabilité unique : ouvrir/fermer, poser SL/TP, Trailing     |
//| Stop et Break Even. S'appuie sur CTrade. Gestion d'erreurs incl. |
//+------------------------------------------------------------------+
#ifndef QUANT_TRADE_MANAGER_MQH
#define QUANT_TRADE_MANAGER_MQH

#include <Trade/Trade.mqh>
#include "Logger.mqh"

struct StopConfig
  {
   double atr_sl_mult;
   double atr_tp_mult;
   double trailing_atr_mult;   // 0 = désactivé
   double breakeven_atr_mult;  // profit (en ATR) déclenchant le BE ; 0 = off
  };

class CTradeManager
  {
private:
   CTrade      m_trade;
   StopConfig  m_cfg;
   CLogger    *m_log;
   ulong       m_magic;
public:
   void Init(ulong magic,const StopConfig &cfg,CLogger *log)
     {
      m_cfg=cfg; m_log=log; m_magic=magic;
      m_trade.SetExpertMagicNumber(magic);
      m_trade.SetTypeFillingBySymbol(_Symbol);
     }

   bool Open(const string symbol,int side,double lots,double atr)
     {
      if(lots<=0) return false;
      double price = side>0 ? SymbolInfoDouble(symbol,SYMBOL_ASK)
                            : SymbolInfoDouble(symbol,SYMBOL_BID);
      double sl = side>0 ? price-atr*m_cfg.atr_sl_mult : price+atr*m_cfg.atr_sl_mult;
      double tp = side>0 ? price+atr*m_cfg.atr_tp_mult : price-atr*m_cfg.atr_tp_mult;
      bool ok = side>0 ? m_trade.Buy(lots,symbol,price,sl,tp)
                       : m_trade.Sell(lots,symbol,price,sl,tp);
      if(!ok)
         m_log.Log(LOG_ERROR,StringFormat("Ordre %s échoué ret=%d %s",symbol,m_trade.ResultRetcode(),m_trade.ResultRetcodeDescription()));
      else
         m_log.Log(LOG_INFO,StringFormat("Ordre %s side=%d lots=%.2f",symbol,side,lots));
      return ok;
     }

   // Applique Break Even puis Trailing Stop sur toutes les positions du magic.
   void ManageOpenPositions(double atr)
     {
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=PositionGetTicket(i);
         if(!PositionSelectByTicket(ticket)) continue;
         if(PositionGetInteger(POSITION_MAGIC)!=m_magic) continue;

         string sym=PositionGetString(POSITION_SYMBOL);
         long   type=PositionGetInteger(POSITION_TYPE);
         double open=PositionGetDouble(POSITION_PRICE_OPEN);
         double sl  =PositionGetDouble(POSITION_SL);
         double tp  =PositionGetDouble(POSITION_TP);
         double bid =SymbolInfoDouble(sym,SYMBOL_BID);
         double ask =SymbolInfoDouble(sym,SYMBOL_ASK);
         double cur =(type==POSITION_TYPE_BUY)?bid:ask;
         double new_sl=sl;

         // Break Even
         if(m_cfg.breakeven_atr_mult>0)
           {
            double trigger=atr*m_cfg.breakeven_atr_mult;
            if(type==POSITION_TYPE_BUY && cur-open>=trigger && sl<open) new_sl=open;
            if(type==POSITION_TYPE_SELL&& open-cur>=trigger && (sl>open||sl==0)) new_sl=open;
           }
         // Trailing Stop
         if(m_cfg.trailing_atr_mult>0)
           {
            double dist=atr*m_cfg.trailing_atr_mult;
            if(type==POSITION_TYPE_BUY)  new_sl=MathMax(new_sl,cur-dist);
            if(type==POSITION_TYPE_SELL) new_sl=(new_sl==0)?cur+dist:MathMin(new_sl,cur+dist);
           }
         if(new_sl!=sl && new_sl!=0)
            if(!m_trade.PositionModify(ticket,new_sl,tp))
               m_log.Log(LOG_WARN,StringFormat("PositionModify %I64u ret=%d",ticket,m_trade.ResultRetcode()));
        }
     }

   int CountPositions()
     {
      int n=0;
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         if(PositionGetTicket(i)>0 && PositionGetInteger(POSITION_MAGIC)==m_magic) n++;
        }
      return n;
     }
  };
#endif
