using System;
using System.Runtime.InteropServices;

namespace UHF
{
    public static class RWDev
    {
        private const string DLLNAME = @"RRU9816.dll";

        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int OpenComPort(int Port,
                                             ref byte ComAddr,
                                             byte Baud,
                                             ref int PortHandle);

        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int CloseComPort();

        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int GetReaderInformation(ref byte ComAdr,
                                                      byte[] VersionInfo,
                                                      ref byte ReaderType,
                                                      ref byte TrType,
                                                      ref byte dmaxfre,
                                                      ref byte dminfre,
                                                      ref byte powerdBm,
                                                      ref byte ScanTime,
                                                      ref byte Ant,
                                                      ref byte BeepEn,
                                                      ref byte OutputRep,
                                                      ref byte CheckAnt,
                                                      int FrmHandle);

        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int SetRegion(ref byte ComAdr,
                                           byte dmaxfre,
                                           byte dminfre,
                                           int frmComPortindex);

        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int SetAddress(ref byte ComAdr,
                                            byte ComAdrData,
                                            int frmComPortindex);

        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int SetInventoryScanTime(ref byte ComAdr,
                                                      byte ScanTime,
                                                      int frmComPortindex);

        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int SetBaudRate(ref byte ComAdr,
                                            byte baud,
                                            int frmComPortindex);

        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int SetRfPower(ref byte ComAdr,
                                            byte powerDbm,
                                            int frmComPortindex);

        // GetTagBufferInfo maps to ReadBuffer_G2 from documentation
        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int ReadBuffer_G2(ref byte ComAdr,
                                               ref int Totallen,
                                               ref int CardNum,
                                               byte[] pEPCList,
                                               int FrmHandle);

        // ClearTagBuffer maps to ClearBuffer_G2 from documentation  
        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int ClearBuffer_G2(ref byte ComAdr,
                                                int FrmHandle);

        // GetBufferCnt_G2 from documentation
        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int GetBufferCnt_G2(ref byte ComAdr,
                                                 ref int Count,
                                                 int FrmHandle);

        // CORRECT function from documentation - InventoryBuffer_G2
        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int InventoryBuffer_G2(ref byte ComAdr,
                                                    byte QValue,
                                                    byte Session,
                                                    byte MaskMem,
                                                    byte[] MaskAdr,
                                                    byte MaskLen,
                                                    byte[] MaskData,
                                                    byte MaskFlag,
                                                    byte AdrTID,
                                                    byte LenTID,
                                                    byte TIDFlag,
                                                    byte Target,
                                                    byte InAnt,
                                                    byte Scantime,
                                                    byte Fastflag,
                                                    ref int BufferCount,
                                                    ref int TagNum,
                                                    int FrmHandle);

        // Standard Inventory_G2 from documentation
        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int Inventory_G2(ref byte ComAdr,
                                              byte QValue,
                                              byte Session,
                                              byte MaskMem,
                                              byte[] MaskAdr,
                                              byte MaskLen,
                                              byte[] MaskData,
                                              byte MaskFlag,
                                              byte AdrTID,
                                              byte LenTID,
                                              byte TIDFlag,
                                              byte Target,
                                              byte InAnt,
                                              byte Scantime,
                                              byte Fastflag,
                                              byte[] EPClenandEPC,
                                              byte[] Ant,
                                              ref int Totallen,
                                              ref int CardNum,
                                              int FrmHandle);

        // Keep existing GetTagBufferInfo for backward compatibility
        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int GetTagBufferInfo(ref byte ComAdr,
                                                  byte[] Data,
                                                  ref int dataLength,
                                                  int frmComPortindex);

        // Keep existing ClearTagBuffer for backward compatibility  
        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int ClearTagBuffer(ref byte ComAdr,
                                               int frmComPortindex);

        // MISSING FUNCTIONS FROM C# DEMO - ADD THESE!
        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int SetWorkMode(ref byte ComAdr,
                                             byte Read_mode,
                                             int frmComPortindex);

        [DllImport(DLLNAME, CallingConvention = CallingConvention.StdCall)]
        public static extern int SetAntennaMultiplexing(ref byte ComAdr,
                                            byte Ant,
                                            int frmComPortindex);
    }
}