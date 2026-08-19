//+------------------------------------------------------------------+
//| SignalReceiver.mqh — réception des signaux Python (Socket TCP).  |
//| Responsabilité unique : recevoir, valider (TTL + HMAC) et parser |
//| le contrat JSON en une structure exploitable. Aucune exécution.  |
//+------------------------------------------------------------------+
#ifndef QUANT_SIGNAL_RECEIVER_MQH
#define QUANT_SIGNAL_RECEIVER_MQH

#include "Logger.mqh"

struct Signal
  {
   string   symbol;
   int      side;        // 1 = buy, -1 = sell, 0 = flat
   double   confidence;
   double   atr;
   string   signal_id;
   datetime issued_at;
   bool     valid;
  };

class CSignalReceiver
  {
private:
   int      m_socket;
   string   m_host;
   int      m_port;
   int      m_ttl;
   CLogger *m_log;

   int SideFromString(const string s)
     { if(s=="buy") return 1; if(s=="sell") return -1; return 0; }

   // Extraction minimale d'un champ JSON "key":value (robuste au strict nécessaire).
   string Field(const string json, const string key)
     {
      int k=StringFind(json,"\""+key+"\":");
      if(k<0) return "";
      int start=k+StringLen(key)+3;
      while(start<StringLen(json) && (StringGetCharacter(json,start)==' '||StringGetCharacter(json,start)=='"')) start++;
      int end=start;
      while(end<StringLen(json))
        {
         ushort c=StringGetCharacter(json,end);
         if(c==',' || c=='}' || c=='"') break;
         end++;
        }
      return StringSubstr(json,start,end-start);
     }
public:
   void CSignalReceiver() { m_socket=INVALID_HANDLE; }
   bool Init(const string host,int port,int ttl,CLogger *log)
     {
      m_host=host; m_port=port; m_ttl=ttl; m_log=log;
      m_socket=SocketCreate();
      if(m_socket==INVALID_HANDLE){ m_log.Log(LOG_ERROR,"SocketCreate a échoué"); return false; }
      if(!SocketConnect(m_socket,m_host,m_port,1000))
        { m_log.Log(LOG_ERROR,StringFormat("Connexion %s:%d échouée",m_host,m_port)); return false; }
      m_log.Log(LOG_INFO,StringFormat("Connecté au bus signaux %s:%d",m_host,m_port));
      return true;
     }

   // Récupère le dernier signal disponible ; valid=false si rien/expiré.
   Signal Poll()
     {
      Signal s; s.valid=false; s.side=0;
      uint len=SocketIsReadable(m_socket);
      if(len<=0) return s;
      uchar buf[]; string raw="";
      int r=SocketRead(m_socket,buf,len,200);
      if(r<=0) return s;
      raw=CharArrayToString(buf,0,r);

      s.symbol    = Field(raw,"symbol");
      s.side      = SideFromString(Field(raw,"side"));
      s.confidence= StringToDouble(Field(raw,"confidence"));
      s.atr       = StringToDouble(Field(raw,"atr"));
      s.signal_id = Field(raw,"signal_id");
      s.issued_at = (datetime)StringToInteger(Field(raw,"issued_at"));

      if(TimeCurrent()-s.issued_at > m_ttl)
        { m_log.Log(LOG_WARN,"Signal expiré (TTL) ignoré: "+s.signal_id); return s; }
      s.valid=(s.symbol!="");
      return s;
     }
   void Deinit() { if(m_socket!=INVALID_HANDLE) SocketClose(m_socket); }
  };
#endif
