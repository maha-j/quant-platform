//+------------------------------------------------------------------+
//| Logger.mqh — journalisation centralisée + niveaux.               |
//| Responsabilité unique : formater et écrire les logs (fichier +   |
//| terminal). Aucune logique de trading ici.                        |
//+------------------------------------------------------------------+
#ifndef QUANT_LOGGER_MQH
#define QUANT_LOGGER_MQH

enum ENUM_LOG_LEVEL { LOG_DEBUG, LOG_INFO, LOG_WARN, LOG_ERROR };

class CLogger
  {
private:
   ENUM_LOG_LEVEL m_level;
   int            m_handle;
   string         Prefix(ENUM_LOG_LEVEL lvl)
     {
      switch(lvl)
        {
         case LOG_DEBUG: return "DEBUG";
         case LOG_INFO:  return "INFO";
         case LOG_WARN:  return "WARN";
         default:        return "ERROR";
        }
     }
public:
   void CLogger() { m_level=LOG_INFO; m_handle=INVALID_HANDLE; }
   void Init(ENUM_LOG_LEVEL level, const string file)
     {
      m_level=level;
      m_handle=FileOpen(file, FILE_WRITE|FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
      if(m_handle!=INVALID_HANDLE) FileSeek(m_handle,0,SEEK_END);
     }
   void Log(ENUM_LOG_LEVEL lvl, const string msg)
     {
      if(lvl<m_level) return;
      string line=StringFormat("%s [%s] %s", TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS), Prefix(lvl), msg);
      Print(line);
      if(m_handle!=INVALID_HANDLE) { FileWrite(m_handle,line); FileFlush(m_handle); }
     }
   void Deinit() { if(m_handle!=INVALID_HANDLE) FileClose(m_handle); }
  };
#endif
