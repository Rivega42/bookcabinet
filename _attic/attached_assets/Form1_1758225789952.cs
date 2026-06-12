using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using System.Collections;
using System.Resources;
using System.Reflection;
using System.Net;
using System.Threading;
using System.Diagnostics;
using UHF;
using System.IO;
using System.Net.Sockets;
namespace RRU2881Demo
{
    public partial class Form1 : Form
    {
        private byte fComAdr = 0xff; //当前操作的ComAdr
        private int ferrorcode;
        private byte fBaud;
        private double fdminfre;
        private double fdmaxfre;
        private int fCmdRet = 30; //所有执行指令的返回值
        private bool fIsInventoryScan;
        private bool fisinventoryscan_6B;
        private byte[] fOperEPC = new byte[100];
        private byte[] fPassWord = new byte[4];
        private byte[] fOperID_6B = new byte[10];
        ArrayList list = new ArrayList();
        private int CardNum1 =0;
        private string fInventory_EPC_List; //存贮询查列表（如果读取的数据没有变化，则不进行刷新）
        private int frmcomportindex;
        private bool SeriaATflag = false;
        private byte Target = 0;
        private byte InAnt = 0;
        private byte Scantime = 0;
        private byte FastFlag = 0;
        private byte Qvalue = 0;
        private byte Session = 0;
        private int total_turns = 0;//轮数
        private int total_tagnum = 0;//标签数量
        private int total_time = 0;//总时间
        private int targettimes = 0;
        private int CommunicationTime = 0;
        private byte TIDFlag = 0;
        public static byte antinfo = 0;
        private int AA_times = 0;
        public DeviceClass SelectedDevice;
        private static List<DeviceClass> DevList;
        private static SearchCallBack searchCallBack = new SearchCallBack(searchCB);

        /// <summary>
        /// Device Search的回调函数;
        /// </summary>
        private static void searchCB(IntPtr dev, IntPtr data)
        {
            uint ipAddr = 0;
            StringBuilder devname = new StringBuilder(100);
            StringBuilder macAdd = new StringBuilder(100);
            //获取搜索到的设备信息；
            DevControl.tagErrorCode eCode = DevControl.DM_GetDeviceInfo(dev, ref ipAddr, macAdd, devname);
            if (eCode == DevControl.tagErrorCode.DM_ERR_OK)
            {
                //将搜索到的设备加入设备列表；
                DeviceClass device = new DeviceClass(dev, ipAddr, macAdd.ToString(), devname.ToString());
                DevList.Add(device);
            }
            else
            {
                //异常处理；
                string errMsg = ErrorHandling.GetErrorMsg(eCode);
                Log.WriteError(errMsg);
            }

        }
        private static IPAddress getIPAddress(uint interIP)
        {
            return new IPAddress((uint)IPAddress.HostToNetworkOrder((int)interIP));
        }
        public Form1()
        {
            InitializeComponent();
            //初始化设备列表；
            DevList = new List<DeviceClass>();

            //初始化设备控制模块；
            DevControl.tagErrorCode eCode = DevControl.DM_Init(searchCallBack, IntPtr.Zero);
            if (eCode != DevControl.tagErrorCode.DM_ERR_OK)
            {
                //如果初始化失败则关闭程序，并进行异常处理；
                string errMsg = ErrorHandling.HandleError(eCode);
                throw new Exception(errMsg);
            }
        }
        private delegate void WriteLogUnSafe(CustomControl.LogRichTextBox logRichTxt, string strLog, int nType);
        private void WriteLog(CustomControl.LogRichTextBox logRichTxt, string strLog, int nType)
        {
            if (this.InvokeRequired)
            {
                WriteLogUnSafe InvokeWriteLog = new WriteLogUnSafe(WriteLog);
                this.Invoke(InvokeWriteLog, new object[] { logRichTxt, strLog, nType });
            }
            else
            {
                if (nType == 0)
                {
                    logRichTxt.AppendTextEx(strLog, Color.Indigo);
                }
                else
                {
                    logRichTxt.AppendTextEx(strLog, Color.Red);
                }

                logRichTxt.Select(logRichTxt.TextLength, 0);
                logRichTxt.ScrollToCaret();
            }
        }
        /// <summary>
        /// 16进制数组字符串转换
        /// </summary>
        /// <param name="s"></param>
        /// <returns></returns>
        #region 
                private byte[] HexStringToByteArray(string s)
                {
                    s = s.Replace(" ", "");
                    byte[] buffer = new byte[s.Length / 2];
                    for (int i = 0; i < s.Length; i += 2)
                        buffer[i / 2] = (byte)Convert.ToByte(s.Substring(i, 2), 16);
                    return buffer;
                }

                private string ByteArrayToHexString(byte[] data)
                {
                    StringBuilder sb = new StringBuilder(data.Length * 3);
                    foreach (byte b in data)
                        sb.Append(Convert.ToString(b, 16).PadLeft(2, '0'));
                    return sb.ToString().ToUpper();

                }
        #endregion
        /// <summary>
                /// 错误代码
        /// </summary>
        /// <param name="cmdRet"></param>
        /// <returns></returns>
        #region 
                private string GetReturnCodeDesc(int cmdRet)
                {
                    switch (cmdRet)
                    {
                        case 0x00:
                            return "successfully";
                        case 0x01:
                            return "Return before Inventory finished";
                        case 0x02:
                            return "the Inventory-scan-time overflow";
                        case 0x03:
                            return "More Data";
                        case 0x04:
                            return "Reader module MCU is Full";
                        case 0x05:
                            return "Access Password Error";
                        case 0x09:
                            return "Destroy Password Error";
                        case 0x0a:
                            return "Destroy Password Error Cannot be Zero";
                        case 0x0b:
                            return "Tag Not Support the command";
                        case 0x0c:
                            return "Use the commmand,Access Password Cannot be Zero";
                        case 0x0d:
                            return "Tag is protected,cannot set it again";
                        case 0x0e:
                            return "Tag is unprotected,no need to reset it";
                        case 0x10:
                            return "There is some locked bytes,write fail";
                        case 0x11:
                            return "can not lock it";
                        case 0x12:
                            return "is locked,cannot lock it again";
                        case 0x13:
                            return "Parameter Save Fail,Can Use Before Power";
                        case 0x14:
                            return "Cannot adjust";
                        case 0x15:
                            return "Return before Inventory finished";
                        case 0x16:
                            return "Inventory-Scan-Time overflow";
                        case 0x17:
                            return "More Data";
                        case 0x18:
                            return "Reader module MCU is full";
                        case 0x19:
                            return "Not Support Command Or AccessPassword Cannot be Zero";
                        case 0x1A:
                            return "Perform error tag custom function";
                        case 0xF8:
                            return "Antenna connection detect errors";
                        case 0xF9:
                            return "Command execution error";
                        case 0xFA:
                            return "Get Tag,Poor Communication,Inoperable";
                        case 0xFB:
                            return "No Tag Operable";
                        case 0xFC:
                            return "Tag Return ErrorCode";
                        case 0xFD:
                            return "Command length wrong";
                        case 0xFE:
                            return "Illegal command";
                        case 0xFF:
                            return "Parameter Error";
                        case 0x30:
                            return "Communication error";
                        case 0x31:
                            return "CRC checksummat error";
                        case 0x32:
                            return "Return data length error";
                        case 0x33:
                            return "Communication busy";
                        case 0x34:
                            return "Busy,command is being executed";
                        case 0x35:
                            return "ComPort Opened";
                        case 0x36:
                            return "ComPort Closed";
                        case 0x37:
                            return "Invalid Handle";
                        case 0x38:
                            return "Invalid Port";
                        case 0xEE:
                            return "Return Command Error";
                        default:
                            return "";
                    }
                }
                private string GetErrorCodeDesc(int cmdRet)
                {
                    switch (cmdRet)
                    {
                        case 0x00:
                            return "Other error";
                        case 0x03:
                            return "Memory out or pc not support";
                        case 0x04:
                            return "Memory Locked and unwritable";
                        case 0x0b:
                            return "No Power,memory write operation cannot be executed";
                        case 0x0f:
                            return "Not Special Error,tag not support special errorcode";
                        default:
                            return "";
                    }
                }
        #endregion
        private void DisabledForm()
        {
            ////应答模式下
            lxLedControl1.Text = "0";
            lxLedControl2.Text = "0";
            lxLedControl3.Text = "0";
            lxLedControl4.Text = "0";
            lxLedControl5.Text = "0";
            dataGridView1.Rows.Clear();
            dataGridView2.Rows.Clear();
            comboBox_EPC.Items.Clear();
            text_RDVersion.Text = "";
            text_Serial.Text = "";
            timer_answer.Enabled = false;
            btIventoryG2.Text = "Start";
            panel1.Enabled = false;
            panel3.Enabled = false;
            panel4.Enabled = false;
            panel5.Enabled = false;
            panel6.Enabled = false;
            gpb_address.Enabled = false;
            gpb_baud.Enabled = false;
            gpb_GPIO.Enabled = false;
            gpb_beep.Enabled = false;
            gpb_RDVersion.Enabled = false;
            gpb_DBM.Enabled = false;
            gpb_Serial.Enabled = false;
            gpb_Freq.Enabled = false;
            btDefault.Enabled = false;
            btGetInformation.Enabled = false;
            gbp_buff.Enabled = false;
        }
        private void EnabledForm()
        {
            panel1.Enabled = true;
            panel3.Enabled = true;
            panel4.Enabled = true;
            panel5.Enabled = true;
            panel6.Enabled = true;
            gpb_address.Enabled = true;
            gpb_baud.Enabled = true;
            gpb_GPIO.Enabled = true;
            gpb_beep.Enabled = true;
            gpb_RDVersion.Enabled = true;
            gpb_DBM.Enabled = true;
            gpb_Serial.Enabled = true;
            gpb_Freq.Enabled = true;
            btDefault.Enabled = true;
            btGetInformation.Enabled = true;
            gbp_buff.Enabled = true;
        }

        private void SetButtonBold(Button btnBold)
        {
            Font oldFont = btnBold.Font;
            Font newFont = new Font(oldFont, oldFont.Style ^ FontStyle.Bold);
            btnBold.Font = newFont;
        }

        private void SetRadioButtonBold(CheckBox ckBold)
        {
            Font oldFont = ckBold.Font;
            Font newFont = new Font(oldFont, oldFont.Style ^ FontStyle.Bold);
            ckBold.Font = newFont;
        }

        private void Form1_Load(object sender, EventArgs e)
        {
            ComboBox_COM.SelectedIndex = 0;
            ComboBox_baud2.SelectedIndex = 3;
            com_Q.SelectedIndex = 4;
            com_Target.SelectedIndex = 0;
            int i = 0;
            for (i = 0x03; i <= 0xff; i++)
                com_scantime.Items.Add(Convert.ToString(i) + "*100ms");
            com_scantime.SelectedIndex = 7;
            com_S.SelectedIndex = 0;
            DisabledForm();
            radioButton_band1.Checked = true;
            ComboBox_baud.SelectedIndex = 3;
            ComboBox_PowerDbm.SelectedIndex = 26;
            btConnect232.ForeColor = Color.Indigo;
            btDisConnect232.ForeColor = Color.Black;
            SetButtonBold(btConnect232);
           // SetButtonBold(btDisConnect232);
            Maintab.TabPages.Remove(Main_Page3);
            Maintab.TabPages.Remove(Main_Page4);
        }

        private void btConnect232_Click(object sender, EventArgs e)
        {
            int portNum = ComboBox_COM.SelectedIndex +1;
            int FrmPortIndex = 0;
            string strException = string.Empty;
            fBaud = Convert.ToByte(ComboBox_baud2.SelectedIndex);
            if (fBaud > 2)
                fBaud = Convert.ToByte(fBaud + 2);
            fComAdr = 255;//广播地址打开设备
            fCmdRet = RWDev.OpenComPort(portNum, ref fComAdr, fBaud, ref FrmPortIndex);
            if (fCmdRet != 0)
            {
                string strLog = "Connect failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
                return;
            }
            else
            {
                frmcomportindex = FrmPortIndex;
                string strLog = "Connected " + ComboBox_COM.Text + "@" + ComboBox_baud2.Text;
                WriteLog(lrtxtLog, strLog, 0);
            }

            //处理界面元素是否有效
            EnabledForm();
            btConnect232.Enabled = false;
            btDisConnect232.Enabled = true;
            //设置按钮字体颜色
            btConnect232.ForeColor = Color.Black;
            btDisConnect232.ForeColor = Color.Indigo;
            SetButtonBold(btConnect232);
            SetButtonBold(btDisConnect232);
            btGetInformation_Click(null,null);//获取读写器信息
        }

        private void btDisConnect232_Click(object sender, EventArgs e)
        {
            if (frmcomportindex>0)
                fCmdRet = RWDev.CloseSpecComPort(frmcomportindex);
            if (fCmdRet == 0) frmcomportindex = -1;
            DisabledForm();
            btConnect232.Enabled = true;
            btDisConnect232.Enabled = false;

            btConnect232.ForeColor = Color.Indigo;
            btDisConnect232.ForeColor = Color.Black;
            SetButtonBold(btConnect232);
            SetButtonBold(btDisConnect232);
        }

        private void btFlashCl_Click(object sender, EventArgs e)
        {
            ////应答模式下刷屏
            if (tabControl2.SelectedTab == tabPage3)
            {
                lxLedControl1.Text = "0";
                lxLedControl2.Text = "0";
                lxLedControl3.Text = "0";
                lxLedControl4.Text = "0";
                lxLedControl5.Text = "0";
                dataGridView1.Rows.Clear();
            }
            ////主动模式下刷屏
            if (tabControl2.SelectedTab == tabPage4)
            {
                lxLed_Num.Text = "0";
                lxLed_cmdsud.Text = "0";
                lxLed_toltag.Text = "0";
                lxLed_toltime.Text = "0";
                lxLed_cmdTime.Text = "0";
                dataGridView2.Rows.Clear();
            }
            ////6B标签刷屏
            if (Maintab.SelectedTab == Main_Page3)
            {
                text_R6B.Text = "";
                text_6BUID.Text = "";
                text_Statu6B.Text = "";
            }
            if (tabControl3.SelectedTab == tabPage8)//TCP 服务器
            {
                stcprecv.Clear();
            }
            if (tabControl3.SelectedTab == tabPage9)//TCP 客户端
            {
                ctctrecv.Clear();
                ctctsend.Text = "";
            }
            total_tagnum = 0;
            total_time = System.Environment.TickCount; 
            comboBox_EPC.Items.Clear();
            lrtxtLog.Clear();

        }

        private void btIventoryG2_Click(object sender, EventArgs e)
        {

            timer_answer.Enabled = !timer_answer.Enabled;
            if (timer_answer.Enabled)
            {
                lxLedControl1.Text = "0";
                lxLedControl2.Text = "0";
                lxLedControl3.Text = "0";
                lxLedControl4.Text = "0";
                lxLedControl5.Text = "0";
                dataGridView1.Rows.Clear();
                comboBox_EPC.Items.Clear();
                AA_times = 0;
                Scantime = Convert.ToByte(com_scantime.SelectedIndex + 3);
                Qvalue = Convert.ToByte(com_Q.SelectedIndex);
                Session = Convert.ToByte(com_S.SelectedIndex);
                if (rb_epc.Checked)
                    TIDFlag = 0;
                else
                    TIDFlag = 1;
                total_turns = 0;
                total_tagnum = 0;
                targettimes = Convert.ToInt32(text_target.Text);
                total_time = System.Environment.TickCount;
                fIsInventoryScan = false;
                Target = 0;
                btIventoryG2.BackColor = Color.Indigo;
                btIventoryG2.Text = "Stop";
            }
            else
            {
                btIventoryG2.BackColor = Color.Transparent;
                btIventoryG2.Text = "Start";
            }
        }
        private void inventory()
        {
            byte Ant = 0;
            int CardNum = 0;
            int Totallen = 0;
            int EPClen, m;
            byte[] EPC = new byte[50000];
            int CardIndex;
            string temps, temp;
            temp = "";
            string sEPC;
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            byte MaskFlag = 0;
            byte AdrTID = 0;
            byte LenTID = 0;
            AdrTID = 0;
            LenTID = 6;
            MaskFlag = 0;
            int cbtime = System.Environment.TickCount;
            DataGridViewRow rows = new DataGridViewRow();
            CardNum = 0;
            fCmdRet = RWDev.Inventory_G2(ref fComAdr, Qvalue, Session, MaskMem, MaskAdr, MaskLen, MaskData, MaskFlag, AdrTID, LenTID, TIDFlag, Target, InAnt, Scantime, FastFlag, EPC, ref Ant, ref Totallen, ref CardNum, frmcomportindex);
            total_turns = total_turns + 1;
            int x_time = System.Environment.TickCount - cbtime;//命令时间
            string strLog = "Inventory: " + GetReturnCodeDesc(fCmdRet);
            WriteLog(lrtxtLog, strLog, 0);
           
            if ((fCmdRet == 1) | (fCmdRet == 2) | (fCmdRet == 3) | (fCmdRet == 4))//代表已查找结束，
            {
                byte[] daw = new byte[Totallen];
                Array.Copy(EPC, daw, Totallen);
                temps = ByteArrayToHexString(daw);
                m = 0;
                if (CardNum == 0)
                {
                    if (Session > 1)
                        AA_times = AA_times + 1;
                    return;
                }
                AA_times = 0;
                //antstr = Convert.ToString(Ant, 2).PadLeft(4, '0');
                for (CardIndex = 0; CardIndex < CardNum; CardIndex++)
                {
                    EPClen = daw[m] + 1;
                    temp = temps.Substring(m * 2 + 2, EPClen * 2);
                    sEPC = temp.Substring(0, temp.Length - 2);
                    string RSSI = Convert.ToInt32(temp.Substring(temp.Length - 2, 2), 16).ToString();
                    m = m + EPClen + 1;
                    if (sEPC.Length != (EPClen - 1) * 2)
                    {
                        return;
                    }
                    bool isonlistview = false;
                    for (int i = 0; i < dataGridView1.RowCount; i++)
                    {
                        if ((dataGridView1.Rows[i].Cells[1].Value != null) && (sEPC == dataGridView1.Rows[i].Cells[1].Value.ToString()))
                        {
                            rows = dataGridView1.Rows[i];
                            int ntime = Convert.ToInt32(rows.Cells[2].Value.ToString());
                            ntime = ntime + 1;
                            if (ntime == 99999) ntime = 1;
                            rows.Cells[2].Value = ntime;
                            rows.Cells[3].Value = RSSI;
                            isonlistview = true;
                            break;
                        }
                    }
                    if (!isonlistview)
                    {
                        string[] arr = new string[4];
                        arr[0] = (dataGridView1.RowCount + 1).ToString();
                        arr[1] = sEPC;
                        arr[2] = "1";
                        arr[3] = RSSI;
                        dataGridView1.Rows.Insert(dataGridView1.RowCount, arr);
                        if (rb_epc.Checked)
                            comboBox_EPC.Items.Add(sEPC);
                    }
                }
            }
            lxLedControl3.Text = x_time.ToString();
            if (x_time > CommunicationTime)
                x_time = x_time - CommunicationTime;//减去通讯时间等于标签的实际时间
            int sulv = (CardNum * 1000) / x_time;//速度等于张数/时间
            lxLedControl2.Text = sulv.ToString();
            total_tagnum = total_tagnum + CardNum;
            lxLedControl4.Text = total_tagnum.ToString();
            x_time = System.Environment.TickCount - total_time;//总时间
            lxLedControl5.Text = x_time.ToString();
            lxLedControl1.Text = dataGridView1.RowCount.ToString();
        }
        private void timer_answer_Tick(object sender, EventArgs e)
        {
            if (fIsInventoryScan)
                return;
            fIsInventoryScan = true;
            FastFlag = 1;
            InAnt = 0x80;
            if (Session == 0 || Session == 1)
            {
                Target = (byte)com_Target.SelectedIndex;
            }
            else
            {
                if ((check_num.Checked) && (AA_times + 1 > targettimes))
                {
                    Target = Convert.ToByte(1 - Target);  //如果连续2次未读到卡片，A/B状态切换。
                }
                else if (!check_num.Checked)
                {
                    Target = (byte)com_Target.SelectedIndex;
                }
            }
            inventory();
            fIsInventoryScan = false;
        }

        private void radioButton_band1_CheckedChanged(object sender, EventArgs e)
        {
            int i;
            ComboBox_dmaxfre.Items.Clear();
            ComboBox_dminfre.Items.Clear();
            for (i = 0; i < 20; i++)
            {
                ComboBox_dminfre.Items.Add(Convert.ToString(920.125 + i * 0.25) + " MHz");
                ComboBox_dmaxfre.Items.Add(Convert.ToString(920.125 + i * 0.25) + " MHz");
            }
            ComboBox_dmaxfre.SelectedIndex = 19;
            ComboBox_dminfre.SelectedIndex = 0;
        }

        private void radioButton_band2_CheckedChanged(object sender, EventArgs e)
        {
            int i;
            ComboBox_dmaxfre.Items.Clear();
            ComboBox_dminfre.Items.Clear();
            for (i = 0; i < 50; i++)
            {
                ComboBox_dminfre.Items.Add(Convert.ToString(902.75 + i * 0.5) + " MHz");
                ComboBox_dmaxfre.Items.Add(Convert.ToString(902.75 + i * 0.5) + " MHz");
            }
            ComboBox_dmaxfre.SelectedIndex = 49;
            ComboBox_dminfre.SelectedIndex = 0;
        }

        private void radioButton_band3_CheckedChanged(object sender, EventArgs e)
        {
            int i;
            ComboBox_dmaxfre.Items.Clear();
            ComboBox_dminfre.Items.Clear();
            for (i = 0; i < 32; i++)
            {
                ComboBox_dminfre.Items.Add(Convert.ToString(917.1 + i * 0.2) + " MHz");
                ComboBox_dmaxfre.Items.Add(Convert.ToString(917.1 + i * 0.2) + " MHz");
            }
            ComboBox_dmaxfre.SelectedIndex = 31;
            ComboBox_dminfre.SelectedIndex = 0;
        }

        private void radioButton_band4_CheckedChanged(object sender, EventArgs e)
        {
            int i;
            ComboBox_dminfre.Items.Clear();
            ComboBox_dmaxfre.Items.Clear();
            for (i = 0; i < 15; i++)
            {
                ComboBox_dminfre.Items.Add(Convert.ToString(865.1 + i * 0.2) + " MHz");
                ComboBox_dmaxfre.Items.Add(Convert.ToString(865.1 + i * 0.2) + " MHz");
            }
            ComboBox_dmaxfre.SelectedIndex = 14;
            ComboBox_dminfre.SelectedIndex = 0;
        }

        private void CheckBox_SameFre_CheckedChanged(object sender, EventArgs e)
        {
            if (CheckBox_SameFre.Checked)
                ComboBox_dmaxfre.SelectedIndex = ComboBox_dminfre.SelectedIndex;
        }

     

        private bool CheckCRC(string s)
        {
            int i, j;
            int current_crc_value;
            byte crcL, crcH;
            byte[] data = HexStringToByteArray(s);
            current_crc_value = 0xFFFF;
            for (i = 0; i <= (data.Length - 1); i++)
            {
                current_crc_value = current_crc_value ^ (data[i]);
                for (j = 0; j < 8; j++)
                {
                    if ((current_crc_value & 0x01) != 0)
                        current_crc_value = (current_crc_value >> 1) ^ 0x8408;
                    else
                        current_crc_value = (current_crc_value >> 1);
                }
            }
            crcL = Convert.ToByte(current_crc_value & 0xFF);
            crcH = Convert.ToByte((current_crc_value >> 8) & 0xFF);
            if (crcH == 0 && crcL==0)
            {
                return true;
            }
            else
            {
                return false;
            }
            
        }

        private void GetData()
        {
            int TagNum = 0;
            int BufferCount = 0;
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            byte MaskFlag = 0;
            byte AdrTID = 0;
            byte LenTID = 0;
            AdrTID = 0;
            LenTID = 6;
            MaskFlag = 0;
            int cbtime = System.Environment.TickCount;
            DataGridViewRow rows = new DataGridViewRow();
            TagNum = 0;
            BufferCount = 0;
            Target = 0;
            Scantime = 0x03;
            Qvalue = 4;
            Session = 1;
            FastFlag = 1;
            fCmdRet = RWDev.InventoryBuffer_G2(ref fComAdr, Qvalue, Session, MaskMem, MaskAdr, MaskLen, MaskData, MaskFlag, AdrTID, LenTID, TIDFlag, Target, InAnt, Scantime, FastFlag, ref BufferCount, ref TagNum, frmcomportindex);
            total_turns = total_turns + 1;
            int x_time = System.Environment.TickCount - cbtime;//命令时间
            string strLog = "Inventory buffer: " + GetReturnCodeDesc(fCmdRet);
            WriteLog(lrtxtLog, strLog, 0);
            ///////////设置网络断线重连
            if (fCmdRet == 0)//代表已查找结束，
            {
                lxLed_cmdTime.Text = x_time.ToString();
                total_tagnum = total_tagnum + TagNum;
                int sulv = (TagNum * 1000) / x_time;//速度等于张数/时间
                lxLed_cmdsud.Text = sulv.ToString();
                lxLed_toltag.Text = total_tagnum.ToString();
                x_time = System.Environment.TickCount - total_time;//总时间
                lxLed_toltime.Text = x_time.ToString();
                lxLed_Num.Text = BufferCount.ToString();
            }       
        }
        private void timer_runmode_Tick(object sender, EventArgs e)
        {
            if (fIsInventoryScan) 
                return;
            fIsInventoryScan = true;
            GetData();
            fIsInventoryScan = false;
        }


        private void Maintab_SelectedIndexChanged(object sender, EventArgs e)
        {
            timer_runmode.Enabled = false;
            timer_answer.Enabled = false;
            timer_EAS.Enabled = false;
            Timer_Test_6B.Enabled = false;
            btIventoryG2.Text = "Start";
            btStartBuff.Text = "Start";
            btCheckEASAlarm.Text = "Detect";
            pictureBox2.Visible = false;
            btIventoryG2.BackColor = Color.Transparent;
            btStartBuff.BackColor = Color.Transparent;
            btInventory6B.Text = "Start";
            btInventory6B.BackColor = Color.Transparent;
            if (comboBox_EPC.Text =="" && comboBox_EPC.Items.Count>0)
            {
                comboBox_EPC.SelectedIndex = 0;
            }
        }

        private void btClearBuffer_Click(object sender, EventArgs e)
        {
            fCmdRet = RWDev.ClearTagBuffer(ref fComAdr, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Clear buffer failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Clear buffer success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btGettagbuffer_Click(object sender, EventArgs e)
        {
            byte[] Data = new byte[8000];
            int dataLength = 0;
            int nLen, NumLen;
            string temp = "";
            string temp1 = "";
            string syear = "";
            string smonth = "";
            string sday = "";
            string shour = "";
            string smin = "";
            string ssec = "";
            string Lyear = "";
            string Lmonth = "";
            string Lday = "";
            string Lhour = "";
            string Lmin = "";
            string Lsec = "";
            string binarystr1 = "";
            string binarystr2 = "";
            string CountStr = "";
            string AntStr = "";
            string EPCStr = "";
            dataGridView2.Rows.Clear();
            lxLed_Num.Text = "0";
            lxLed_cmdsud.Text = "0";
            lxLed_toltag.Text = "0";
            lxLed_toltime.Text = "0";
            total_time = System.Environment.TickCount;
            fCmdRet = RWDev.GetTagBufferInfo(ref fComAdr, Data, ref dataLength, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Read Buffer failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                nLen = dataLength * 2;
                temp = ByteArrayToHexString(Data);
                while (nLen > 0)
                {
                    NumLen = 24 + Convert.ToInt32(temp.Substring(22, 2), 16) * 2;
                    temp1 = temp.Substring(0, NumLen);
                    binarystr1 = Convert.ToString(Convert.ToInt32(temp1.Substring(0, 8), 16), 2).PadLeft(32, '0');
                    syear = Convert.ToString(Convert.ToInt32(binarystr1.Substring(0, 6), 2)).PadLeft(2, '0');
                    smonth = Convert.ToString(Convert.ToInt32(binarystr1.Substring(6, 4), 2)).PadLeft(2, '0');
                    sday = Convert.ToString(Convert.ToInt32(binarystr1.Substring(10, 5), 2)).PadLeft(2, '0');
                    shour = Convert.ToString(Convert.ToInt32(binarystr1.Substring(15, 5), 2)).PadLeft(2, '0');
                    smin = Convert.ToString(Convert.ToInt32(binarystr1.Substring(20, 6), 2)).PadLeft(2, '0');
                    ssec = Convert.ToString(Convert.ToInt32(binarystr1.Substring(26, 6), 2)).PadLeft(2, '0');

                    binarystr2 = Convert.ToString(Convert.ToInt32(temp1.Substring(8, 8), 16), 2).PadLeft(32, '0');
                    Lyear = Convert.ToString(Convert.ToInt32(binarystr2.Substring(0, 6), 2)).PadLeft(2, '0');
                    Lmonth = Convert.ToString(Convert.ToInt32(binarystr2.Substring(6, 4), 2)).PadLeft(2, '0');
                    Lday = Convert.ToString(Convert.ToInt32(binarystr2.Substring(10, 5), 2)).PadLeft(2, '0');
                    Lhour = Convert.ToString(Convert.ToInt32(binarystr2.Substring(15, 5), 2)).PadLeft(2, '0');
                    Lmin = Convert.ToString(Convert.ToInt32(binarystr2.Substring(20, 6), 2)).PadLeft(2, '0');
                    Lsec = Convert.ToString(Convert.ToInt32(binarystr2.Substring(26, 6), 2)).PadLeft(2, '0');

                    CountStr = Convert.ToString(Convert.ToInt32(temp1.Substring(16, 4), 16), 10);

                    AntStr = Convert.ToString(Convert.ToInt32(temp1.Substring(20, 2), 16), 2).PadLeft(4, '0');
                    EPCStr = temp1.Substring(24, temp1.Length - 24);

                    string[] arr = new string[6];
                    arr[0] = (dataGridView2.RowCount + 1).ToString();
                    arr[1] = EPCStr;
                    arr[2] = "20" + syear + "-" + smonth + "-" + sday + " " + shour + ":" + smin + ":" + ssec;
                    arr[3] = "20" + Lyear + "-" + Lmonth + "-" + Lday + " " + Lhour + ":" + Lmin + ":" + Lsec;
                    arr[4] = AntStr;
                    arr[5] = CountStr;
                    dataGridView2.Rows.Insert(dataGridView2.RowCount, arr);
                    if ((temp.Length - NumLen) > 0)
                        temp = temp.Substring(NumLen, temp.Length - NumLen);
                    nLen = nLen - NumLen;
                }
                string strLog = "Read Buffer success ";
                WriteLog(lrtxtLog, strLog, 0);
                int xtime = System.Environment.TickCount - total_time;
                lxLed_Num.Text = dataGridView2.RowCount.ToString();
                lxLed_cmdsud.Text = (dataGridView2.RowCount * 1000 / xtime).ToString();
                lxLed_toltag.Text = dataGridView2.RowCount.ToString();
                lxLed_toltime.Text = xtime.ToString();
            }
        }


        private void tb_Port_KeyPress(object sender, KeyPressEventArgs e)
        {
            e.Handled = ("0123456789".IndexOf(Char.ToUpper(e.KeyChar)) < 0);
        }

        private void text_address_KeyPress(object sender, KeyPressEventArgs e)
        {
            e.Handled = ("0123456789ABCDEF".IndexOf(Char.ToUpper(e.KeyChar)) < 0);
        }

        private void btGetInformation_Click(object sender, EventArgs e)
        {
            byte TrType = 0;
            byte[] VersionInfo = new byte[2];
            byte ReaderType = 0;
            byte ScanTime = 0;
            byte dmaxfre = 0;
            byte dminfre = 0;
            byte powerdBm = 0;
            byte FreBand = 0;
            byte Ant = 0;
            byte BeepEn = 0;
            byte OutputRep = 0;
            byte CheckAnt = 0;
            text_RDVersion.Text = "";
            int ctime = System.Environment.TickCount;
            fCmdRet = RWDev.GetReaderInformation(ref fComAdr, VersionInfo, ref ReaderType, ref TrType, ref dmaxfre, ref dminfre, ref powerdBm, ref ScanTime, ref Ant, ref BeepEn, ref OutputRep, ref CheckAnt, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Get Reader Information failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                CommunicationTime = System.Environment.TickCount - ctime;
                text_RDVersion.Text = Convert.ToString(VersionInfo[0], 10).PadLeft(2, '0') + "." + Convert.ToString(VersionInfo[1], 10).PadLeft(2, '0');

                ComboBox_PowerDbm.SelectedIndex = Convert.ToInt32(powerdBm);
                text_address.Text = Convert.ToString(fComAdr, 16).PadLeft(2, '0');
                FreBand = Convert.ToByte(((dmaxfre & 0xc0) >> 4) | (dminfre >> 6));
                switch (FreBand)
                {
                    case 1:
                        {
                            radioButton_band1.Checked = true;
                            fdminfre = 920.125 + (dminfre & 0x3F) * 0.25;
                            fdmaxfre = 920.125 + (dmaxfre & 0x3F) * 0.25;
                        }
                        break;
                    case 2:
                        {
                            radioButton_band2.Checked = true;
                            fdminfre = 902.75 + (dminfre & 0x3F) * 0.5;
                            fdmaxfre = 902.75 + (dmaxfre & 0x3F) * 0.5;
                        }
                        break;
                    case 3:
                        {
                            radioButton_band3.Checked = true;
                            fdminfre = 917.1 + (dminfre & 0x3F) * 0.2;
                            fdmaxfre = 917.1 + (dmaxfre & 0x3F) * 0.2;
                        }
                        break;
                    case 4:
                        {
                            radioButton_band4.Checked = true;
                            fdminfre = 865.1 + (dminfre & 0x3F) * 0.2;
                            fdmaxfre = 865.1 + (dmaxfre & 0x3F) * 0.2;
                        }
                        break;
                }
                if (fdmaxfre != fdminfre)
                    CheckBox_SameFre.Checked = false;
                ComboBox_dminfre.SelectedIndex = dminfre & 0x3F;
                ComboBox_dmaxfre.SelectedIndex = dmaxfre & 0x3F;
                switch (BeepEn)
                {
                    case 1:
                        Radio_beepEn.Checked = true;
                        break;
                    case 0:
                        Radio_beepDis.Checked = true;
                        break;
                }
       
                string strLog = "Get Reader Information success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btDefault_Click(object sender, EventArgs e)
        {
            byte aNewComAdr, powerDbm, dminfre, dmaxfre, scantime;
            dminfre = 64;
            dmaxfre = 19;
            aNewComAdr = 0x00;
            powerDbm = 30;
            fBaud = 5;
            scantime = 10;
            ComboBox_baud.SelectedIndex = 3;
            fCmdRet = RWDev.SetAddress(ref fComAdr, aNewComAdr, frmcomportindex);
             if (fCmdRet != 0)
            {
                string strLog = "Set address failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Set address access ";
                WriteLog(lrtxtLog, strLog, 0);
            }

             fCmdRet = RWDev.SetRfPower(ref fComAdr, powerDbm, frmcomportindex);
             if (fCmdRet != 0)
             {
                 string strLog = "Set power failed: " + GetReturnCodeDesc(fCmdRet);
                 WriteLog(lrtxtLog, strLog, 1);
             }
             else
             {
                 string strLog = "Set power success ";
                 WriteLog(lrtxtLog, strLog, 0);
             }

             fCmdRet = RWDev.SetRegion(ref fComAdr, dmaxfre, dminfre, frmcomportindex);
             if (fCmdRet != 0)
             {
                 string strLog = "Set Region failed: " + GetReturnCodeDesc(fCmdRet);
                 WriteLog(lrtxtLog, strLog, 1);
             }
             else
             {
                 string strLog = "Set Region success ";
                 WriteLog(lrtxtLog, strLog, 0);
             }

             fCmdRet = RWDev.SetBaudRate(ref fComAdr, fBaud, frmcomportindex);
             if (fCmdRet != 0)
             {
                 string strLog = "Set baud rate failed: " + GetReturnCodeDesc(fCmdRet);
                 WriteLog(lrtxtLog, strLog, 1);
             }
             else
             {
                 string strLog = "Set baud rate success ";
                 WriteLog(lrtxtLog, strLog, 0);
             }

             fCmdRet = RWDev.SetInventoryScanTime(ref fComAdr, scantime, frmcomportindex);
             if (fCmdRet != 0)
             {
                 string strLog = "Set max inventory time failed: " + GetReturnCodeDesc(fCmdRet);
                 WriteLog(lrtxtLog, strLog, 1);
             }
             else
             {
                 string strLog = "Set max inventory time success ";
                 WriteLog(lrtxtLog, strLog, 0);
             }
             btGetInformation_Click(null,null);
        }

        private void btaddress_Click(object sender, EventArgs e)
        {
            byte aNewComAdr = Convert.ToByte(text_address.Text,16);
            fCmdRet = RWDev.SetAddress(ref fComAdr, aNewComAdr, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Set address failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Set address access ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btFreq_Click(object sender, EventArgs e)
        {
            byte dminfre, dmaxfre;
            int band = 2;
            if (radioButton_band1.Checked)
                band = 1;
            if (radioButton_band2.Checked)
                band = 2;
            if (radioButton_band3.Checked)
                band = 3;
            if (radioButton_band4.Checked)
                band = 4;
            dminfre = Convert.ToByte(((band & 3) << 6) | (ComboBox_dminfre.SelectedIndex & 0x3F));
            dmaxfre = Convert.ToByte(((band & 0x0c) << 4) | (ComboBox_dmaxfre.SelectedIndex & 0x3F));
            fCmdRet = RWDev.SetRegion(ref fComAdr, dmaxfre, dminfre, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Set Region failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Set Region success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void BT_DBM_Click(object sender, EventArgs e)
        {
            byte powerDbm = (byte)ComboBox_PowerDbm.SelectedIndex;
            fCmdRet = RWDev.SetRfPower(ref fComAdr, powerDbm, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Set power failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Set power success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btBaudRate_Click(object sender, EventArgs e)
        {
            byte fBaud = (byte)ComboBox_baud.SelectedIndex;
            if (fBaud > 2)
                fBaud = (byte)(fBaud + 2);
            fCmdRet = RWDev.SetBaudRate(ref fComAdr, fBaud, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Set baud rate failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Set baud rate success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btSerial_Click(object sender, EventArgs e)
        {
            byte[] SeriaNo = new byte[4];
            text_Serial.Text = "";
            fCmdRet = RWDev.GetSeriaNo(ref fComAdr, SeriaNo, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Reader serial number failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                text_Serial.Text = ByteArrayToHexString(SeriaNo);
                string strLog = "Reader serial number success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

      
        private void Button_Beep_Click(object sender, EventArgs e)
        {
            byte BeepEn = 0;
            if (Radio_beepEn.Checked)
                BeepEn = 1;
            else
                BeepEn = 0;
            fCmdRet = RWDev.SetBeepNotification(ref fComAdr, BeepEn, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Set beep failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Set beep success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

     
        private void Button_SetGPIO_Click(object sender, EventArgs e)
        {
            byte OutputPin = 0;
            if (check_out1.Checked)
                OutputPin = Convert.ToByte(OutputPin | 0x01);
            if (check_out2.Checked)
                OutputPin = Convert.ToByte(OutputPin | 0x02);
            fCmdRet = RWDev.SetGPIO(ref fComAdr, OutputPin, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Set GPIO failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Set GPIO success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void Button_GetGPIO_Click(object sender, EventArgs e)
        {
            byte OutputPin = 0;
            fCmdRet = RWDev.GetGPIOStatus(ref fComAdr, ref OutputPin, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Get GPIO status failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                if ((OutputPin & 0x10) == 0x10)
                    check_out1.Checked = true;
                else
                    check_out1.Checked = false;

                if ((OutputPin & 0x20) == 0x20)
                    check_out2.Checked = true;
                else
                    check_out2.Checked = false;

                if ((OutputPin & 0x01) == 1)
                    check_int1.Checked = true;
                else
                    check_int1.Checked = false;

                if ((OutputPin & 0x02) == 2)
                    check_int2.Checked = true;
                else
                    check_int2.Checked = false;

                string strLog = "Get GPIO status success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }


        private void btSelectTag_Click(object sender, EventArgs e)
        {
            text_epc.Text = comboBox_EPC.Text;
        }

        private void checkBox1_CheckedChanged(object sender, EventArgs e)
        {
            if (checkBox1.Checked)
            {
                maskadr_textbox.Enabled = true;
                maskLen_textBox.Enabled = true;
                maskData_textBox.Enabled = true;
                R_EPC.Enabled = true;
                R_TID.Enabled = true;
                R_User.Enabled = true;
            }
            else
            {
                maskadr_textbox.Enabled = false;
                maskLen_textBox.Enabled = false;
                maskData_textBox.Enabled = false;
                R_EPC.Enabled = false;
                R_TID.Enabled = false;
                R_User.Enabled = false;
            }
        }

        private void btRead_Click(object sender, EventArgs e)
        {
            byte WordPtr, ENum;
            byte Num = 0;
            byte Mem = 0;
            string str = ""; ;
            byte[] CardData = new byte[320];
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            text_WriteData.Text = "";
            if (checkBox1.Checked)
            {
                if ((maskadr_textbox.Text == "") || (maskLen_textBox.Text == "") || (maskData_textBox.Text == ""))
                {
                    return;
                }
                ENum = 255;
                if (R_EPC.Checked) MaskMem = 1;
                if (R_TID.Checked) MaskMem = 2;
                if (R_User.Checked) MaskMem = 3;
                MaskAdr = HexStringToByteArray(maskadr_textbox.Text);
                MaskLen = Convert.ToByte(maskLen_textBox.Text, 16);
                MaskData = HexStringToByteArray(maskData_textBox.Text);
            }
            else
            {
                if (check_selecttag.Checked)
                    str = text_epc.Text;
                else
                    str = "";
                ENum = Convert.ToByte(str.Length / 4);
            }
            byte[] EPC = new byte[ENum * 2];
            EPC = HexStringToByteArray(str);
            if (C_Reserve.Checked)
                Mem = 0;
            if (C_EPC.Checked)
                Mem = 1;
            if (C_TID.Checked)
                Mem = 2;
            if (C_User.Checked)
                Mem = 3;
            if (text_WordPtr.Text == "" || text_RWlen.Text == "" || text_AccessCode2.Text.Length != 8)
            {
                return;
            }
            WordPtr = Convert.ToByte(text_WordPtr.Text, 16);
            Num = Convert.ToByte(text_RWlen.Text);
            fPassWord = HexStringToByteArray(text_AccessCode2.Text);
            for (int p = 0; p < 10; p++)
            {
                fCmdRet = RWDev.ReadData_G2(ref fComAdr, EPC, ENum, Mem, WordPtr, Num, fPassWord, MaskMem, MaskAdr, MaskLen, MaskData, CardData, ref ferrorcode, frmcomportindex);
                if(fCmdRet==0)break;
            }
            if (fCmdRet != 0)
            {

                string strLog = "";
                if (fCmdRet == 0xFC)
                        strLog = "Read data failed: " + "tag return error =0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                    else
                        strLog = "Read data failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                byte[] daw = new byte[Num * 2];
                Array.Copy(CardData, daw, Num * 2);
                text_WriteData.Text = ByteArrayToHexString(daw);
                string strLog = "Read data success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btWrite_Click(object sender, EventArgs e)
        {
            byte WordPtr, ENum;
            byte WNum = 0;
            byte Mem = 0;
            string str = ""; ;
            byte[] CardData = new byte[320];
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            if (checkBox1.Checked)
            {
                if ((maskadr_textbox.Text == "") || (maskLen_textBox.Text == "") || (maskData_textBox.Text == ""))
                {
                    return;
                }
                ENum = 255;
                if (R_EPC.Checked) MaskMem = 1;
                if (R_TID.Checked) MaskMem = 2;
                if (R_User.Checked) MaskMem = 3;
                MaskAdr = HexStringToByteArray(maskadr_textbox.Text);
                MaskLen = Convert.ToByte(maskLen_textBox.Text, 16);
                MaskData = HexStringToByteArray(maskData_textBox.Text);
            }
            else
            {
                if (check_selecttag.Checked)
                    str = text_epc.Text;
                else
                    str = "";
                ENum = Convert.ToByte(str.Length / 4);
            }
            byte[] EPC = new byte[ENum * 2];
            EPC = HexStringToByteArray(str);
            if (C_Reserve.Checked)
                Mem = 0;
            if (C_EPC.Checked)
                Mem = 1;
            if (C_TID.Checked)
                Mem = 2;
            if (C_User.Checked)
                Mem = 3;
            if (text_WordPtr.Text == "" || text_AccessCode2.Text.Length != 8)
            {
                return;
            }
            string epcstr=text_WriteData.Text;
            if (epcstr.Length % 4 != 0 || epcstr.Length==0)
            {
                MessageBox.Show("Input data by word.", "Information");
                return;
            }
            WNum = Convert.ToByte(epcstr.Length / 4);
            byte[] Writedata = new byte[WNum * 2 + 1];
            Writedata = HexStringToByteArray(epcstr);
            WordPtr = Convert.ToByte(text_WordPtr.Text, 16);
            fPassWord = HexStringToByteArray(text_AccessCode2.Text);
            if ((checkBox_pc.Checked) && (C_EPC.Checked))
            {
                WordPtr = 1;
                WNum = Convert.ToByte(epcstr.Length / 4 + 1);
                Writedata = HexStringToByteArray(textBox_pc.Text + epcstr);
            }
            for (int p = 0; p < 10; p++)
            {
                fCmdRet = RWDev.WriteData_G2(ref fComAdr, EPC, WNum, ENum, Mem, WordPtr, Writedata, fPassWord, MaskMem, MaskAdr, MaskLen, MaskData, ref ferrorcode, frmcomportindex);
                if (fCmdRet == 0) break;
            }
            if (fCmdRet != 0)
            {
                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Write data failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Write data failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Write data success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void checkBox_pc_CheckedChanged(object sender, EventArgs e)
        {
            if (checkBox_pc.Checked && C_EPC.Checked)
            {
                text_WordPtr.Text = "0002";
                text_WordPtr.ReadOnly = true;
                int m, n;
                n = text_WriteData.Text.Length;
                if (n % 4 == 0)
                {
                    m = n / 4;
                    m = (m & 0x3F) << 3;
                    textBox_pc.Text = Convert.ToString(m, 16).PadLeft(2, '0') + "00";
                }
            }
            else
            {
                text_WordPtr.ReadOnly = false;
            }
        }

        private void text_WriteData_TextChanged(object sender, EventArgs e)
        {
            int m, n;
            n = text_WriteData.Text.Length;
            if ((checkBox_pc.Checked) && (n % 4 == 0) && (C_EPC.Checked))
            {
                m = n / 4;
                m = (m & 0x3F) << 3;
                textBox_pc.Text = Convert.ToString(m, 16).PadLeft(2, '0') + "00";
            }
        }

        private void C_EPC_CheckedChanged(object sender, EventArgs e)
        {
            if (checkBox_pc.Checked && C_EPC.Checked)
            {
                text_WordPtr.Text = "0002";
                text_WordPtr.ReadOnly = true;
            }
            else
            {
                text_WordPtr.ReadOnly = false;
            }
        }

        private void btBlockWrite_Click(object sender, EventArgs e)
        {
            byte WordPtr, ENum;
            byte WNum = 0;
            byte Mem = 0;
            string str = ""; ;
            byte[] CardData = new byte[320];
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            if (checkBox1.Checked)
            {
                if ((maskadr_textbox.Text == "") || (maskLen_textBox.Text == "") || (maskData_textBox.Text == ""))
                {
                    return;
                }
                ENum = 255;
                if (R_EPC.Checked) MaskMem = 1;
                if (R_TID.Checked) MaskMem = 2;
                if (R_User.Checked) MaskMem = 3;
                MaskAdr = HexStringToByteArray(maskadr_textbox.Text);
                MaskLen = Convert.ToByte(maskLen_textBox.Text, 16);
                MaskData = HexStringToByteArray(maskData_textBox.Text);
            }
            else
            {
                if (check_selecttag.Checked)
                    str = text_epc.Text;
                else
                    str = "";
                ENum = Convert.ToByte(str.Length / 4);
            }
            byte[] EPC = new byte[ENum * 2];
            EPC = HexStringToByteArray(str);
            if (C_Reserve.Checked)
                Mem = 0;
            if (C_EPC.Checked)
                Mem = 1;
            if (C_TID.Checked)
                Mem = 2;
            if (C_User.Checked)
                Mem = 3;
            if (text_WordPtr.Text == "" || text_AccessCode2.Text.Length != 8)
            {
                return;
            }
            string epcstr = text_WriteData.Text;
            if (epcstr.Length % 4 != 0 || epcstr.Length == 0)
            {
                MessageBox.Show("Input data by word.", "Information");
                return;
            }
            WNum = Convert.ToByte(epcstr.Length / 4);
            byte[] Writedata = new byte[WNum * 2 + 1];
            Writedata = HexStringToByteArray(epcstr);
            WordPtr = Convert.ToByte(text_WordPtr.Text, 16);
            fPassWord = HexStringToByteArray(text_AccessCode2.Text);
            if ((checkBox_pc.Checked) && (C_EPC.Checked))
            {
                WordPtr = 1;
                WNum = Convert.ToByte(epcstr.Length / 4 + 1);
                Writedata = HexStringToByteArray(textBox_pc.Text + epcstr);
            }
            for (int p = 0; p < 10; p++)
            {
                fCmdRet = RWDev.BlockWrite_G2(ref fComAdr, EPC, WNum, ENum, Mem, WordPtr, Writedata, fPassWord, MaskMem, MaskAdr, MaskLen, MaskData, ref ferrorcode, frmcomportindex);
                if(fCmdRet==0)break;
            }
            if (fCmdRet != 0)
            {
                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Block write failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Block write failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Block write success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btBlockErase_Click(object sender, EventArgs e)
        {
            byte WordPtr, ENum;
            byte Num = 0;
            byte Mem = 0;
            string str = ""; ;
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            text_WriteData.Text = "";
            if (checkBox1.Checked)
            {
                if ((maskadr_textbox.Text == "") || (maskLen_textBox.Text == "") || (maskData_textBox.Text == ""))
                {
                    return;
                }
                ENum = 255;
                if (R_EPC.Checked) MaskMem = 1;
                if (R_TID.Checked) MaskMem = 2;
                if (R_User.Checked) MaskMem = 3;
                MaskAdr = HexStringToByteArray(maskadr_textbox.Text);
                MaskLen = Convert.ToByte(maskLen_textBox.Text, 16);
                MaskData = HexStringToByteArray(maskData_textBox.Text);
            }
            else
            {
                if (check_selecttag.Checked)
                    str = text_epc.Text;
                else
                    str = "";
                ENum = Convert.ToByte(str.Length / 4);
            }
            byte[] EPC = new byte[ENum * 2];
            EPC = HexStringToByteArray(str);
            if (C_Reserve.Checked)
                Mem = 0;
            if (C_EPC.Checked)
                Mem = 1;
            if (C_TID.Checked)
                Mem = 2;
            if (C_User.Checked)
                Mem = 3;
            if (text_WordPtr.Text == "" || text_RWlen.Text == "" || text_AccessCode2.Text.Length != 8)
            {
                return;
            }
            WordPtr = Convert.ToByte(text_WordPtr.Text, 16);
            Num = Convert.ToByte(text_RWlen.Text);
            fPassWord = HexStringToByteArray(text_AccessCode2.Text);
            fCmdRet = RWDev.BlockErase_G2(ref fComAdr, EPC, ENum, Mem, WordPtr, Num, fPassWord, MaskMem, MaskAdr, MaskLen, MaskData, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {

                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Block erase failed: " + "tag return error=0x" + Convert.ToString(ferrorcode,16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Block erase failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Block erase success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btSetProtectState_Click(object sender, EventArgs e)
        {
            byte select = 0;
            byte setprotect = 0;
            string str="";
            byte ENum;
            byte[] CardData = new byte[320];
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
           
            if (checkBox1.Checked)
            {
                if ((maskadr_textbox.Text == "") || (maskLen_textBox.Text == "") || (maskData_textBox.Text == ""))
                {
                    return;
                }
                ENum = 255;
                if (R_EPC.Checked) MaskMem = 1;
                if (R_TID.Checked) MaskMem = 2;
                if (R_User.Checked) MaskMem = 3;
                MaskAdr = HexStringToByteArray(maskadr_textbox.Text);
                MaskLen = Convert.ToByte(maskLen_textBox.Text, 16);
                MaskData = HexStringToByteArray(maskData_textBox.Text);
            }
            else
            {
                if (check_selecttag.Checked)
                    str = text_epc.Text;
                else
                    str = "";
                ENum = Convert.ToByte(str.Length / 4);
            }
            byte[] EPC = new byte[ENum * 2];
            EPC = HexStringToByteArray(str);
            if (Edit_AccessCode6.Text.Length != 8)
            {
                return;
            }
            fPassWord = HexStringToByteArray(Edit_AccessCode6.Text);
            if (P_kill.Checked)
                select = 0x00;
            else if (p_pass.Checked)
                select = 0x01;
            else if (P_EPC.Checked)
                select = 0x02;
            else if (P_TID.Checked)
                select = 0x03;
            else if (P_User.Checked)
                select = 0x04;

            if (NoProect2.Checked)
                setprotect = 0x00;
            else if (Proect2.Checked)
                setprotect = 0x02;
            else if (Always2.Checked)
            {
                setprotect = 0x01;
                if (MessageBox.Show(this, "Unlock forever?", "information", MessageBoxButtons.OKCancel) == DialogResult.Cancel)
                    return;
            }
            else if (AlwaysNot2.Checked)
            {
                setprotect = 0x03;
                if (MessageBox.Show(this, "Lock forever?", "information", MessageBoxButtons.OKCancel) == DialogResult.Cancel)
                    return;
            }
            fCmdRet = RWDev.Lock_G2(ref fComAdr, EPC, ENum, select, setprotect, fPassWord, MaskMem, MaskAdr, MaskLen, MaskData, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {

                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Lock failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Lock failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Lock success ";
                WriteLog(lrtxtLog, strLog, 0);
            }

        }

        private void btDestroyCard_Click(object sender, EventArgs e)
        {
            string str = "";
            byte ENum;
            byte[] CardData = new byte[320];
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            if (checkBox1.Checked)
            {
                if ((maskadr_textbox.Text.Length != 4) || (maskLen_textBox.Text.Length != 2) || (maskData_textBox.Text.Length % 2 != 0) && (maskData_textBox.Text.Length == 0))
                {
                    return;
                }
                ENum = 255;
                if (R_EPC.Checked) MaskMem = 1;
                if (R_TID.Checked) MaskMem = 2;
                if (R_User.Checked) MaskMem = 3;
                MaskAdr = HexStringToByteArray(maskadr_textbox.Text);
                MaskLen = Convert.ToByte(maskLen_textBox.Text, 16);
                MaskData = HexStringToByteArray(maskData_textBox.Text);
            }
            else
            {
                if (check_selecttag.Checked)
                    str = text_epc.Text;
                else
                    str = "";
                ENum = Convert.ToByte(str.Length / 4);
            }
            byte[] EPC = new byte[ENum * 2];
            EPC = HexStringToByteArray(str);
            if (text_DestroyCode.Text.Length != 8)
            {
                return;
            }
            fPassWord = HexStringToByteArray(text_DestroyCode.Text);
            fCmdRet = RWDev.KillTag_G2(ref fComAdr, EPC, ENum, fPassWord, MaskMem, MaskAdr, MaskLen, MaskData, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {

                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Kill tag failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Kill tag failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Kill tag success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btWriteEPC_G2_Click(object sender, EventArgs e)
        {
            byte[] WriteEPC = new byte[200];
            byte WriteEPClen;
            byte ENum;
            if (text_AccessCode3.Text.Length < 8)
            {
                return;
            }
            if ((text_WriteEPC.Text.Length % 4) != 0 || text_WriteEPC.Text.Length==0)
            {
                MessageBox.Show("Please input Data in words in hexadecimal form!'+#13+#10+'For example: 1234、12345678", "information");
                return;
            }
            WriteEPClen = Convert.ToByte(text_WriteEPC.Text.Length / 2);
            ENum = Convert.ToByte(text_WriteEPC.Text.Length / 4);
            byte[] EPC = new byte[ENum];
            EPC = HexStringToByteArray(text_WriteEPC.Text);
            fPassWord = HexStringToByteArray(text_AccessCode3.Text);
            fCmdRet = RWDev.WriteEPC_G2(ref fComAdr, fPassWord, EPC, ENum, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {

                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Write EPC failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Write EPC failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                if (comboBox_EPC.Items.IndexOf(text_WriteEPC.Text) == -1)
                    comboBox_EPC.Items.Add(text_WriteEPC.Text);
                string strLog = "Write EPC success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
         
        }

        private void btSetReadProtect_G2_Click(object sender, EventArgs e)
        {
            string str = "";
            byte ENum;
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            if (checkBox1.Checked)
            {
                if (checkBox1.Checked)
                {
                    if ((maskadr_textbox.Text.Length != 4) || (maskLen_textBox.Text.Length != 2) || (maskData_textBox.Text.Length % 2 != 0) && (maskData_textBox.Text.Length == 0))
                    {
                        return;
                    }
                }
                ENum = 255;
                if (R_EPC.Checked) MaskMem = 1;
                if (R_TID.Checked) MaskMem = 2;
                if (R_User.Checked) MaskMem = 3;
                MaskAdr = HexStringToByteArray(maskadr_textbox.Text);
                MaskLen = Convert.ToByte(maskLen_textBox.Text, 16);
                MaskData = HexStringToByteArray(maskData_textBox.Text);
            }
            else
            {
                if (check_selecttag.Checked)
                    str = text_epc.Text;
                else
                    str = "";
                ENum = Convert.ToByte(str.Length / 4);
            }
            byte[] EPC = new byte[ENum * 2];
            EPC = HexStringToByteArray(str);
            if (text_AccessCode4.Text.Length != 8)
            {
                return;
            }
            fPassWord = HexStringToByteArray(text_AccessCode4.Text);
            fCmdRet = RWDev.SetPrivacyByEPC_G2(ref fComAdr, EPC, ENum, fPassWord, MaskMem, MaskAdr, MaskLen, MaskData, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {

                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Set Privacy by EPC failed:" + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Set Privacy by EPC failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Set Privacy by EPC success ";
                WriteLog(lrtxtLog, strLog, 0);
            }           
        }

        private void btSetMultiReadProtect_G2_Click(object sender, EventArgs e)
        {
            if (text_AccessCode4.Text.Length != 8)
            {
                return;
            }
            fPassWord = HexStringToByteArray(text_AccessCode4.Text);
            fCmdRet = RWDev.SetPrivacyWithoutEPC_G2(ref fComAdr, fPassWord, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {

                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Set privacy without EPC failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Set privacy without EPC failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Set privacy without EPC success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btRemoveReadProtect_G2_Click(object sender, EventArgs e)
        {
            if (text_AccessCode4.Text.Length != 8)
            {
                return;
            }
            fPassWord = HexStringToByteArray(text_AccessCode4.Text);
            fCmdRet = RWDev.ResetPrivacy_G2(ref fComAdr, fPassWord, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {

                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Reset privacy failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Reset privacy failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Reset privacy success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btCheckReadProtected_G2_Click(object sender, EventArgs e)
        {
            byte readpro = 2;
            fCmdRet = RWDev.CheckPrivacy_G2(ref fComAdr, ref readpro, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {

                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Check privacy failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Check privacy failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog="";
                if (readpro == 0)
                    strLog = " 'Check privacy success'command return=0x00" + "(Single Tag is unprotected)";
                if (readpro == 1)
                    strLog = " 'Check privacy success'command return=0x01" + "(Single Tag is protected)";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btSetEASAlarm_G2_Click(object sender, EventArgs e)
        {
            byte EAS = 0;
            byte ENum;
            string str="";
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            text_WriteData.Text = "";
            if (checkBox1.Checked)
            {
                if ((maskadr_textbox.Text == "") || (maskLen_textBox.Text == "") || (maskData_textBox.Text == ""))
                {
                    return;
                }
                ENum = 255;
                if (R_EPC.Checked) MaskMem = 1;
                if (R_TID.Checked) MaskMem = 2;
                if (R_User.Checked) MaskMem = 3;
                MaskAdr = HexStringToByteArray(maskadr_textbox.Text);
                MaskLen = Convert.ToByte(maskLen_textBox.Text, 16);
                MaskData = HexStringToByteArray(maskData_textBox.Text);
            }
            else
            {
                if (check_selecttag.Checked)
                    str = text_epc.Text;
                else
                    str = "";
                ENum = Convert.ToByte(str.Length / 4);
            }
            byte[] EPC = new byte[ENum * 2];
            EPC = HexStringToByteArray(str);
            if (text_AccessCode5.Text.Length != 8)
            {
                return;
            }
            fPassWord = HexStringToByteArray(text_AccessCode5.Text);
            if (Alarm_G2.Checked)
                EAS = 1;
            else
                EAS = 0;
            fCmdRet = RWDev.EASConfigure_G2(ref fComAdr, EPC, ENum, fPassWord, EAS, MaskMem, MaskAdr, MaskLen, MaskData, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "EAS Configure failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "";
                if (Alarm_G2.Checked )
                    strLog = " 'EAS Configure' command return=0x00" + "(Set EAS Alarm successfully)";
                else
                    strLog = " 'EAS Configure' command return=0x00" + "(Clear EAS Alarm successfully)";
                WriteLog(lrtxtLog, strLog, 0);
            }

        }

        private void btCheckEASAlarm_Click(object sender, EventArgs e)
        {
            timer_EAS.Enabled = !timer_EAS.Enabled;
            if (!timer_EAS.Enabled)
            {
                pictureBox2.Visible = false; 
                btCheckEASAlarm.Text = "Detect";
                btCheckEASAlarm.BackColor = Color.Transparent;
            }
            else
            {
                fIsInventoryScan = false;
                btCheckEASAlarm.Text = "Stop";
                btCheckEASAlarm.BackColor = Color.Indigo;
            }
        }

        private void timer_EAS_Tick(object sender, EventArgs e)
        {
            if (fIsInventoryScan)
                return;
            fIsInventoryScan = true;
            fCmdRet = RWDev.EASAlarm_G2(ref fComAdr, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "No EAS Alarm";
                WriteLog(lrtxtLog, strLog, 1);
                pictureBox2.Visible = false; 
            }
            else
            {
                pictureBox2.Visible = true;
                string strLog = "EAS Alarm";
                WriteLog(lrtxtLog, strLog, 0);
            }
            fIsInventoryScan = false;
        }

        private void btInventory6B_Click(object sender, EventArgs e)
        {
            Timer_Test_6B.Enabled = !Timer_Test_6B.Enabled;
            if (!Timer_Test_6B.Enabled)
            {
                btInventory6B.Text = "Start";
                btInventory6B.BackColor = Color.Transparent;
            }
            else
            {
                fisinventoryscan_6B = false;
                ListView_ID_6B.Items.Clear();
                btInventory6B.BackColor = Color.Indigo;
                btInventory6B.Text = "Stop";
            }
        }
        public void ChangeSubItem1(ListViewItem ListItem, int subItemIndex, string ItemText, string ant, string RSSI)
        {
            if (subItemIndex == 1)
            {
                if (ListItem.SubItems[subItemIndex].Text != ItemText)
                {
                    ListItem.SubItems[subItemIndex].Text = ItemText;
                    ListItem.SubItems[subItemIndex + 2].Text = "1";
                    ListItem.SubItems[subItemIndex + 1].Text = ant;
                }
                else
                {
                    ListItem.SubItems[subItemIndex + 2].Text = Convert.ToString(Convert.ToUInt32(ListItem.SubItems[subItemIndex + 2].Text) + 1);
                    if ((Convert.ToUInt32(ListItem.SubItems[subItemIndex + 2].Text) > 9999))
                        ListItem.SubItems[subItemIndex + 2].Text = "1";
                    ListItem.SubItems[subItemIndex + 1].Text = Convert.ToString(Convert.ToInt32(ListItem.SubItems[subItemIndex + 1].Text, 2) | Convert.ToInt32(ant, 2), 2).PadLeft(4, '0');

                }
                ListItem.SubItems[subItemIndex + 3].Text = RSSI;
            }
        }
        private void Inventory_6B()
        {
            int CardNum = 0;
            byte[] ID_6B = new byte[2000];
            byte[] ID2_6B = new byte[5000];
            bool isonlistview;
            string temps;
            string s, ss, sID;
            ListViewItem aListItem = new ListViewItem();
            int i, j;
            byte Condition = 0;
            byte StartAddress;
            byte mask = 0;
            byte[] ConditionContent = new byte[300];
            byte ant = 0;
            if (rb_single.Checked)
            {
                fCmdRet = RWDev.InventorySingle_6B(ref fComAdr, ref ant, ID_6B, frmcomportindex);
                if (fCmdRet == 0)
                {
                    byte[] daw = new byte[10];
                    Array.Copy(ID_6B, daw, 10);
                    temps = ByteArrayToHexString(daw);
                    string RSSI = daw[9].ToString();
                    temps = temps.Substring(2, 16);

                    if (!list.Contains(temps))
                    {
                        CardNum1 = CardNum1 + 1;
                        list.Add(temps);
                    }
                    string sant = Convert.ToString(ant, 2).PadLeft(4, '0');
                    isonlistview = false;
                    for (i = 0; i < ListView_ID_6B.Items.Count; i++)     //判断是否在ListView列表内
                    {
                        if (temps == ListView_ID_6B.Items[i].SubItems[1].Text)
                        {
                            aListItem = ListView_ID_6B.Items[i];
                            ChangeSubItem1(aListItem, 1, temps, sant, RSSI);
                            isonlistview = true;
                            break;
                        }
                    }
                    if (!isonlistview)
                    {
                        aListItem = ListView_ID_6B.Items.Add((ListView_ID_6B.Items.Count + 1).ToString());
                        aListItem.SubItems.Add("");
                        aListItem.SubItems.Add("");
                        aListItem.SubItems.Add("");
                        aListItem.SubItems.Add("");
                        aListItem.SubItems.Add("");
                        s = temps;
                        ChangeSubItem1(aListItem, 1, s, sant, RSSI);
                    }
                }
            }
            if (rb_mutiple.Checked)
            {
                Condition = 1;
                ss = "0000000000000000";//4种条件这里选择的是非全0的标签
                byte[] daw = HexStringToByteArray(ss);
                mask = 0xFF;
                StartAddress = 0;
                CardNum = 0;
                fCmdRet = RWDev.InventoryMultiple_6B(ref fComAdr, Condition, StartAddress, mask, daw, ref ant, ID2_6B, ref CardNum, frmcomportindex);
                if ((fCmdRet == 0x15) | (fCmdRet == 0x16) | (fCmdRet == 0x17) | (fCmdRet == 0x18) | (fCmdRet == 0xFB))
                {
                    byte[] daw1 = new byte[CardNum * 10];
                    Array.Copy(ID2_6B, daw1, CardNum * 10);
                    temps = ByteArrayToHexString(daw1);
                    string sant = Convert.ToString(ant, 2).PadLeft(4, '0');
                    for (i = 0; i < CardNum; i++)
                    {
                        sID = temps.Substring(20 * i + 2, 16);
                        string RSSI = temps.Substring(20 * i + 18, 2);
                        RSSI = Convert.ToByte(RSSI, 16).ToString();
                        if ((sID.Length) != 16)
                            return;
                        if (CardNum == 0)
                            return;
                        isonlistview = false;
                        for (j = 0; j < ListView_ID_6B.Items.Count; j++)     //判断是否在Listview列表内
                        {
                            if (sID == ListView_ID_6B.Items[j].SubItems[1].Text)
                            {
                                aListItem = ListView_ID_6B.Items[j];
                                ChangeSubItem1(aListItem, 1, sID, sant, RSSI);
                                isonlistview = true;
                                break;
                            }
                        }
                        if (!isonlistview)
                        {
                            aListItem = ListView_ID_6B.Items.Add((ListView_ID_6B.Items.Count + 1).ToString());
                            aListItem.SubItems.Add("");
                            aListItem.SubItems.Add("");
                            aListItem.SubItems.Add("");
                            aListItem.SubItems.Add("");
                            aListItem.SubItems.Add("");
                            s = sID;
                            ChangeSubItem1(aListItem, 1, s, sant, RSSI);
                        }
                    }
                }
            }
            WriteLog(lrtxtLog, "18000-6B Query", 0);
        }
        private void Timer_Test_6B_Tick(object sender, EventArgs e)
        {
            if (fisinventoryscan_6B)
                return;
            fisinventoryscan_6B = true;
            Inventory_6B();
            fisinventoryscan_6B = false;
        }

        private void ListView_ID_6B_DoubleClick(object sender, EventArgs e)
        {
             if (this.ListView_ID_6B.SelectedIndices.Count > 0 && this.ListView_ID_6B.SelectedIndices[0] != -1)
             {
                 text_6BUID.Text = ListView_ID_6B.SelectedItems[0].SubItems[1].Text;
             }
        }
        //E004000085D94502
        private void btRead6B_Click(object sender, EventArgs e)
        {
            string temp, temps;
            byte[] CardData = new byte[320];
            byte[] ID_6B = new byte[8];
            byte Num, StartAddress;
            if (text_6BUID.Text == "")
            {
                MessageBox.Show("Select one tag in the list");
                return;
            }
            temp = text_6BUID.Text;
            ID_6B = HexStringToByteArray(temp);
            if (text_R6BAddr.Text == "")
                return;
            StartAddress = Convert.ToByte(text_R6BAddr.Text, 16);
            if (text_R6BLen.Text == "")
                return;
            Num = Convert.ToByte(text_R6BLen.Text,16);
            fCmdRet = RWDev.ReadData_6B(ref fComAdr, ID_6B, StartAddress, Num, CardData, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Read data failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Read data failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                byte[] data = new byte[Num];
                Array.Copy(CardData, data, Num);
                temps = ByteArrayToHexString(data);
                text_R6B.Text = temps;
                string strLog = "Read data success ";
                WriteLog(lrtxtLog, strLog, 0);
            }   
        }

        private void btWrite6B_Click(object sender, EventArgs e)
        {
            string temp;
            byte[] CardData = new byte[320];
            byte[] ID_6B = new byte[8];
            byte StartAddress;
            byte Writedatalen;
            int writtenbyte = 0;
            if (text_6BUID.Text == "")
            {
                MessageBox.Show("Select one tag in the list");
                return;
            }
            temp = text_6BUID.Text;
            ID_6B = HexStringToByteArray(temp);
            if (text_W6BAddr.Text == "")
                return;
            StartAddress = Convert.ToByte(text_W6BAddr.Text, 16);
            if (text_W6BLen.Text == "")
                return;
            Writedatalen = Convert.ToByte(text_W6BLen.Text, 16);

            if ((text_W6B.Text == "") | ((text_W6B.Text.Length / 2) != Writedatalen) | ((text_W6B.Text.Length % 2) != 0))
                return;
            byte[] Writedata = new byte[Writedatalen];
            Writedata = HexStringToByteArray(text_W6B.Text);
            fCmdRet = RWDev.WriteData_6B(ref fComAdr, ID_6B, StartAddress, Writedata, Writedatalen, ref writtenbyte, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Write data failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Write data failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Write data success ";
                WriteLog(lrtxtLog, strLog, 0);
            }   

        }

        private void text_W6BLen_TextChanged(object sender, EventArgs e)
        {
            text_W6B.MaxLength = Convert.ToInt32(text_W6BLen.Text,16)*2;
        }

        private void btLock6B_Click(object sender, EventArgs e)
        {
            byte Address;
            string temps;
            byte[] ID_6B = new byte[8];
            if (text_6BUID.Text == "")
            {
                MessageBox.Show("Select one tag in the list");
                return;
            }
            temps = text_6BUID.Text;
            ID_6B = HexStringToByteArray(temps);
            if (text_lock6b.Text == "")
                return;
            Address = Convert.ToByte(text_lock6b.Text,16);
            if (MessageBox.Show(this, "Lock forever?", "information", MessageBoxButtons.OKCancel) == DialogResult.Cancel)
                return;
            fCmdRet = RWDev.Lock_6B(ref fComAdr, ID_6B, Address, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Lock failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Lock failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Lock success ";
                WriteLog(lrtxtLog, strLog, 0);
            }   

        }

        private void btCheckLock6B_Click(object sender, EventArgs e)
        {
            byte Address, ReLockState = 2;
            string temps;
            byte[] ID_6B = new byte[8];
            if (text_6BUID.Text == "")
            {
                MessageBox.Show("Select one tag in the list");
                return;
            }
            temps = text_6BUID.Text;
            ID_6B = HexStringToByteArray(temps);
            if (text_checkaddr.Text == "")
                return;
            Address = Convert.ToByte(text_checkaddr.Text,16);
            fCmdRet = RWDev.CheckLock_6B(ref fComAdr, ID_6B, Address, ref ReLockState, ref ferrorcode, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Detect lock failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Detect lock failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "";
                if (ReLockState == 0)
                    text_Statu6B.Text = "Unlocked";
                if (ReLockState == 1)
                    text_Statu6B.Text = "Locked";
                strLog = "Detect lock success ";
                WriteLog(lrtxtLog, strLog, 0);
            }   
          
        }

        private void btGetSeriaPort_Click(object sender, EventArgs e)
        {
            try
            {
                SeriaATflag = false;
                byte timeout = 0;
                byte cmdlen = 0;
                byte[] data = new byte[100];
                byte[] cmddata = new byte[100];
                byte recvLen = 0;
                byte[] recvdata = new byte[1000];
                string cmd = "AT!SP?";
                data = Encoding.ASCII.GetBytes(cmd);
                cmdlen = Convert.ToByte(cmd.Length);
                Array.Copy(data, cmddata, cmdlen);
                timeout = 30;
                cmddata[cmdlen] = 0x0d;
                cmddata[cmdlen + 1] = 0x0a;
                cmdlen = Convert.ToByte(cmdlen + 2);
                fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                if (fCmdRet != 0)
                {
                    string strLog = "AT CMD failed: " + GetReturnCodeDesc(fCmdRet);
                    WriteLog(lrtxtLog, strLog, 1);
                }
                else
                {
                    string recvs = Encoding.ASCII.GetString(recvdata);
                    if ((recvs.IndexOf("ERROR") > 0) || (recvLen == 0))
                    {
                        MessageBox.Show("Read failed!", "Information");
                        SeriaATflag = true;
                        return;
                    }
                    int m = 0;
                    int n = 0;
                    protocolCB.SelectedIndex = 0;
                    string code = "";
                    m = recvs.IndexOf(":");
                    recvs = recvs.Substring(m + 2);
                    n = recvs.IndexOf(",");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);

                    n = recvs.IndexOf(",");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);

                    n = recvs.IndexOf(",");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);
                    baudrateCB.SelectedIndex = Convert.ToInt32(code);

                    n = recvs.IndexOf(",");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);
                    databitCB.SelectedIndex = Convert.ToInt32(code);

                    n = recvs.IndexOf(",");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);
                    stopbitCB.SelectedIndex = Convert.ToInt32(code);

                    n = recvs.IndexOf(",");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);
                    parityCB.SelectedIndex = Convert.ToInt32(code);

                    n = recvs.IndexOf(",");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);
                    flowCB.SelectedIndex = Convert.ToInt32(code);

                    n = recvs.IndexOf("\r\n");
                    code = recvs.Substring(0, n);
                    fifoCB.SelectedIndex = Convert.ToInt32(code);
                    string strLog = "AT CMD success ";
                    WriteLog(lrtxtLog, strLog, 0);
                }
            }
            catch (System.Exception ex)
            {
                ex.ToString();
            }
        }

        private void btSetSerialPort_Click(object sender, EventArgs e)
        {
            try
            {
                byte timeout = 0;
                byte cmdlen = 0;
                byte[] data = new byte[100];
                byte[] cmddata = new byte[100];
                byte recvLen = 0;
                byte[] recvdata = new byte[1000];
                string cmd = "AT!SP=0,1,";
                cmd = cmd + baudrateCB.SelectedIndex.ToString() + "," + databitCB.SelectedIndex.ToString()
                    + "," + stopbitCB.SelectedIndex.ToString() + "," + parityCB.SelectedIndex.ToString()
                    + "," + flowCB.SelectedIndex.ToString() + "," + fifoCB.SelectedIndex.ToString();
                data = Encoding.ASCII.GetBytes(cmd);
                cmdlen = Convert.ToByte(cmd.Length);
                Array.Copy(data, cmddata, cmdlen);
                timeout = 30;
                cmddata[cmdlen] = 0x0d;
                cmddata[cmdlen + 1] = 0x0a;
                cmdlen = Convert.ToByte(cmdlen + 2);
                fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                if (fCmdRet != 0)
                {
                    string strLog = "AT CMD failed: " + GetReturnCodeDesc(fCmdRet);
                    WriteLog(lrtxtLog, strLog, 1);
                }
                else
                {
                    string recvs = Encoding.ASCII.GetString(recvdata);
                    if ((recvs.IndexOf("ERROR") > 0) || (recvLen == 0))
                    {
                        MessageBox.Show("Set failed!", "Information");
                    }
                    string strLog = "AT CMD success ";
                    WriteLog(lrtxtLog, strLog, 0);
                }
            }
            catch (System.Exception ex)
            {
                ex.ToString();
            }
        }

        private void btGetCnt_Click(object sender, EventArgs e)
        {
            try
            {
                SeriaATflag = false;
                byte timeout = 0;
                byte cmdlen = 0;
                byte[] data = new byte[100];
                byte[] cmddata = new byte[100];
                byte recvLen = 0;
                byte[] recvdata = new byte[1000];
                string cmd = "AT!TC?";
                data = Encoding.ASCII.GetBytes(cmd);
                cmdlen = Convert.ToByte(cmd.Length);
                Array.Copy(data, cmddata, cmdlen);
                timeout = 30;
                cmddata[cmdlen] = 0x0d;
                cmddata[cmdlen + 1] = 0x0a;
                cmdlen = Convert.ToByte(cmdlen + 2);
                fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                if (fCmdRet != 0)
                {
                    string strLog = "AT CMD failed: " + GetReturnCodeDesc(fCmdRet);
                    WriteLog(lrtxtLog, strLog, 1);
                }
                else
                {
                    string recvs = Encoding.ASCII.GetString(recvdata);
                    if ((recvs.IndexOf("ERROR") > 0) || (recvLen == 0))
                    {
                        MessageBox.Show("Read failed!", "information");
                        SeriaATflag = true;
                        return;
                    }
                    int m = 0;
                    int n = 0;
                    string code = "";
                    m = recvs.IndexOf(",");
                    recvs = recvs.Substring(m + 1);
                    n = recvs.IndexOf(",");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);
                    workasCB.SelectedIndex = Convert.ToInt32(code);

                    n = recvs.IndexOf(",");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);
                    tcpActiveCB.SelectedIndex = Convert.ToInt32(code) - 1;

                    n = recvs.IndexOf(",");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);
                    tcpLocalPortNUD.Text = code;

                    if (recvs.IndexOf("1800") > 0)
                    {
                        recvs = recvs.Substring(1);
                        n = recvs.IndexOf("\"");
                        code = recvs.Substring(0, n);
                        recvs = recvs.Substring(n + 2);
                        tcpRomteHostTB.Text = code;

                        n = recvs.IndexOf(",");
                        code = recvs.Substring(0, n);
                        tcpRemotePortNUD.Text = code;
                    }
                    else
                    {
                        n = recvs.IndexOf("\"");
                        code = recvs.Substring(0, n - 1);
                        recvs = recvs.Substring(n + 1);
                        tcpRemotePortNUD.Text = code;

                        n = recvs.IndexOf(",");
                        code = recvs.Substring(0, n - 1);
                        recvs = recvs.Substring(n + 1);
                        tcpRomteHostTB.Text = code;
                    }
                    string strLog = "AT CMD success ";
                    WriteLog(lrtxtLog, strLog, 0);
                }
            }
            catch (System.Exception ex)
            {
                ex.ToString();
            }
        }

        private void btSetCnt_Click(object sender, EventArgs e)
        {
            try
            {
                byte timeout = 0;
                byte cmdlen = 0;
                byte[] data = new byte[100];
                byte[] cmddata = new byte[100];
                byte recvLen = 0;
                byte[] recvdata = new byte[1000];
                string cmd = "AT!TC=0,";
                cmd = cmd + workasCB.SelectedIndex.ToString() + "," + Convert.ToString(tcpActiveCB.SelectedIndex + 1)
                    + "," + tcpLocalPortNUD.Text + ",\"" + tcpRomteHostTB.Text
                    + "\"," + tcpRemotePortNUD.Text + "," + ",";
                data = Encoding.ASCII.GetBytes(cmd);
                cmdlen = Convert.ToByte(cmd.Length);
                Array.Copy(data, cmddata, cmdlen);
                timeout = 30;
                cmddata[cmdlen] = 0x0d;
                cmddata[cmdlen + 1] = 0x0a;
                cmdlen = Convert.ToByte(cmdlen + 2);
                fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                if (fCmdRet != 0)
                {
                    string strLog = "AT CMD failed: " + GetReturnCodeDesc(fCmdRet);
                    WriteLog(lrtxtLog, strLog, 1);
                }
                else
                {
                    string recvs = Encoding.ASCII.GetString(recvdata);
                    if ((recvs.IndexOf("ERROR") > 0) || (recvLen == 0))
                    {
                        Thread.Sleep(500);
                        cmd = "AT!TC=0,";
                        cmd = cmd + workasCB.SelectedIndex.ToString() + "," + Convert.ToString(tcpActiveCB.SelectedIndex + 1)
                            + "," + tcpLocalPortNUD.Text + ",\"" + tcpRemotePortNUD.Text
                            + "\"," + tcpRomteHostTB.Text + "," + ",";
                        data = Encoding.ASCII.GetBytes(cmd);
                        cmdlen = Convert.ToByte(cmd.Length);
                        Array.Copy(data, cmddata, cmdlen);
                        timeout = 30;
                        cmddata[cmdlen] = 0x0d;
                        cmddata[cmdlen + 1] = 0x0a;
                        cmdlen = Convert.ToByte(cmdlen + 2);
                        fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                        if (fCmdRet == 0)
                        {
                            recvs = Encoding.ASCII.GetString(recvdata);
                            if ((recvs.IndexOf("ERROR") > 0) || (recvLen == 0))
                            {
                                MessageBox.Show("Set failed!", "information");
                                return;
                            }
                            string strLog = "AT CMD success ";
                            WriteLog(lrtxtLog, strLog, 0);
                        }
                    }

                }
            }
            catch (System.Exception ex)
            {
                ex.ToString();
            }
        }

        private void btGetNet_Click(object sender, EventArgs e)
        {
            try
            {
                SeriaATflag = false;
                byte timeout = 0;
                byte cmdlen = 0;
                byte[] data = new byte[100];
                byte[] cmddata = new byte[100];
                byte recvLen = 0;
                byte[] recvdata = new byte[1000];
                string cmd = "AT!IC?";
                data = Encoding.ASCII.GetBytes(cmd);
                cmdlen = Convert.ToByte(cmd.Length);
                Array.Copy(data, cmddata, cmdlen);
                timeout = 30;
                cmddata[cmdlen] = 0x0d;
                cmddata[cmdlen + 1] = 0x0a;
                cmdlen = Convert.ToByte(cmdlen + 2);
                fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                if (fCmdRet != 0)
                {
                    string strLog = "AT CMD failed: " + GetReturnCodeDesc(fCmdRet);
                    WriteLog(lrtxtLog, strLog, 1);
                }
                else
                {
                    string recvs = Encoding.ASCII.GetString(recvdata);
                    if ((recvs.IndexOf("ERROR") > 0) || (recvLen == 0))
                    {
                        MessageBox.Show("Read failed!", "information");
                        SeriaATflag = true;
                        return;
                    }
                    int m = 0;
                    int n = 0;
                    string code = "";
                    m = recvs.IndexOf("\"");
                    recvs = recvs.Substring(m + 1);
                    n = recvs.IndexOf("\"");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 3);
                    ipTB.Text = code;

                    n = recvs.IndexOf("\"");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 3);
                    subnetTB.Text = code;

                    n = recvs.IndexOf("\"");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 3);
                    gatewayTB.Text = code;

                    n = recvs.IndexOf("\"");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 3);
                    pDNSTB.Text = code;

                    n = recvs.IndexOf("\"");
                    code = recvs.Substring(0, n);
                    recvs = recvs.Substring(n + 1);
                    altDNSTB.Text = code;
                }

                Thread.Sleep(500);
                cmd = "AT!EC?";
                data = Encoding.ASCII.GetBytes(cmd);
                cmdlen = Convert.ToByte(cmd.Length);
                Array.Copy(data, cmddata, cmdlen);
                timeout = 30;
                cmddata[cmdlen] = 0x0d;
                cmddata[cmdlen + 1] = 0x0a;
                cmdlen = Convert.ToByte(cmdlen + 2);
                fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                if (fCmdRet != 0)
                {
                    string strLog = "AT CMD failed: " + GetReturnCodeDesc(fCmdRet);
                    WriteLog(lrtxtLog, strLog, 1);
                }
                else
                {
                    string recvs = Encoding.ASCII.GetString(recvdata);
                    if ((recvs.IndexOf("ERROR") > 0) || (recvLen == 0))
                    {
                        MessageBox.Show("Read failed!", "information");
                        SeriaATflag = true;
                        return;
                    }
                    int m = 0;
                    int n = 0;
                    string code = "";
                    m = recvs.IndexOf("\"");
                    recvs = recvs.Substring(m + 1);
                    n = recvs.IndexOf("\"");
                    code = recvs.Substring(0, n);
                    macTB.Text = code;
                    string strLog = "AT CMD success ";
                    WriteLog(lrtxtLog, strLog, 0);
                }
            }
            catch (System.Exception ex)
            {
                ex.ToString();
            }
        }

        private void btSetNet_Click(object sender, EventArgs e)
        {
            try
            {
                byte timeout = 0;
                byte cmdlen = 0;
                byte[] data = new byte[100];
                byte[] cmddata = new byte[100];
                byte recvLen = 0;
                byte[] recvdata = new byte[1000];
                string cmd = "AT!IC=0,\"";
                cmd = cmd + ipTB.Text + "\",\"" + subnetTB.Text
                    + "\",\"" + gatewayTB.Text + "\",\"" + pDNSTB.Text
                    + "\",\"" + altDNSTB.Text + "\"";
                data = Encoding.ASCII.GetBytes(cmd);
                cmdlen = Convert.ToByte(cmd.Length);
                Array.Copy(data, cmddata, cmdlen);
                timeout = 30;
                cmddata[cmdlen] = 0x0d;
                cmddata[cmdlen + 1] = 0x0a;
                cmdlen = Convert.ToByte(cmdlen + 2);
                fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                if (fCmdRet != 0)
                {
                    string strLog = "AT CMD failed: " + GetReturnCodeDesc(fCmdRet);
                    WriteLog(lrtxtLog, strLog, 1);
                }
                else
                {
                    string recvs = Encoding.ASCII.GetString(recvdata);
                    if ((recvs.IndexOf("ERROR") > 0) || (recvLen == 0))
                    {
                        Thread.Sleep(500);
                        cmd = "AT!IC=0,\"";
                        cmd = cmd + ipTB.Text + "\","
                            + ",\"" + gatewayTB.Text + "\",\"" + pDNSTB.Text
                            + "\",\"" + altDNSTB.Text + "\"";
                        data = Encoding.ASCII.GetBytes(cmd);
                        cmdlen = Convert.ToByte(cmd.Length);
                        Array.Copy(data, cmddata, cmdlen);
                        timeout = 60;
                        cmddata[cmdlen] = 0x0d;
                        cmddata[cmdlen + 1] = 0x0a;
                        cmdlen = Convert.ToByte(cmdlen + 2);
                        fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                        if (fCmdRet == 0)
                        {
                            recvs = Encoding.ASCII.GetString(recvdata);
                            if ((recvs.IndexOf("ERROR") > 0) || (recvLen == 0))
                            {
                                MessageBox.Show("Set failed!", "information");
                                return;
                            }
                        }
                    }
                    string strLog = "AT CMD success";
                    WriteLog(lrtxtLog, strLog, 0);
                }
            }
            catch (System.Exception ex)
            {
                ex.ToString();
            }
        }

        private void btLoadDefault_Click(object sender, EventArgs e)
        {
            try
            {
                byte timeout = 0;
                byte cmdlen = 0;
                byte[] data = new byte[100];
                byte[] cmddata = new byte[100];
                byte recvLen = 0;
                byte[] recvdata = new byte[1000];
                string cmd = "AT!LD";
                data = Encoding.ASCII.GetBytes(cmd);
                cmdlen = Convert.ToByte(cmd.Length);
                Array.Copy(data, cmddata, cmdlen);
                timeout = 30;
                cmddata[cmdlen] = 0x0d;
                cmddata[cmdlen + 1] = 0x0a;
                cmdlen = Convert.ToByte(cmdlen + 2);
                fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                if (fCmdRet != 0)
                {
                    string strLog = "AT CMD failed: " + GetReturnCodeDesc(fCmdRet);
                    WriteLog(lrtxtLog, strLog, 1);
                }
                else
                {
                    string recvs = Encoding.ASCII.GetString(recvdata);
                    if ((recvs.IndexOf("ERROR") > 0) || (recvLen == 0))
                    {
                        MessageBox.Show("Set failed!", "information");
                        return;
                    }
                    string strLog = "AT CMD success";
                    WriteLog(lrtxtLog, strLog, 0);
                }
            }
            catch (System.Exception ex)
            {
                ex.ToString();
            }
        }

        private void btSave_Click(object sender, EventArgs e)
        {
            try
            {
                byte timeout = 0;
                byte cmdlen = 0;
                byte[] data = new byte[100];
                byte[] cmddata = new byte[100];
                byte recvLen = 0;
                byte[] recvdata = new byte[1000];
                string cmd = "AT!S";
                data = Encoding.ASCII.GetBytes(cmd);
                cmdlen = Convert.ToByte(cmd.Length);
                Array.Copy(data, cmddata, cmdlen);
                timeout = 30;
                cmddata[cmdlen] = 0x0d;
                cmddata[cmdlen + 1] = 0x0a;
                cmdlen = Convert.ToByte(cmdlen + 2);
                fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                if (fCmdRet != 0)
                {
                    string strLog = "AT CMD failed: " + GetReturnCodeDesc(fCmdRet);
                    WriteLog(lrtxtLog, strLog, 1);
                }
                else
                {
                    Thread.Sleep(500);
                    cmd = "AT!R";
                    data = Encoding.ASCII.GetBytes(cmd);
                    cmdlen = Convert.ToByte(cmd.Length);
                    Array.Copy(data, cmddata, cmdlen);
                    timeout = 30;
                    cmddata[cmdlen] = 0x0d;
                    cmddata[cmdlen + 1] = 0x0a;
                    cmdlen = Convert.ToByte(cmdlen + 2);
                    fCmdRet = RWDev.TransparentCMD(ref fComAdr, timeout, cmdlen, cmddata, ref recvLen, recvdata, frmcomportindex);
                    string strLog = "AT CMD success ";
                    WriteLog(lrtxtLog, strLog, 0);
                }
            }
            catch (System.Exception ex)
            {
                ex.ToString();
            }
        }

        private void btGotoAT_Click(object sender, EventArgs e)
        {
            byte ATMode = 1;
            SeriaATflag = false;
            fCmdRet = RWDev.ChangeATMode(ref fComAdr, ATMode, frmcomportindex);
            if (fCmdRet != 0)
            {
                SeriaATflag = true;
                string strLog = "Goto AT mode failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Goto AT mode success ";
                WriteLog(lrtxtLog, strLog, 0);
            }   
        }

        private void btExitAT_Click(object sender, EventArgs e)
        {
            byte ATMode = 0;
            fCmdRet = RWDev.ChangeATMode(ref fComAdr, ATMode, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Exit AT mode failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Exit AT mode success ";
                WriteLog(lrtxtLog, strLog, 0);
            }   
        }
        /// <summary>
        /// 将Device List中所记录设备显示至DeviceListView控件;
        /// </summary>
        private void ReflashDeviceListView(List<DeviceClass> deviceList)
        {
            this.DeviceListView.Items.Clear();
            foreach (DeviceClass device in deviceList)
            {
                IPAddress ipAddr = getIPAddress(device.DeviceIP);
                ListViewItem deviceListViewItem = new ListViewItem(new string[] { device.DeviceName, ipAddr.ToString(), device.DeviceMac });
                deviceListViewItem.ImageIndex = 0;
                this.DeviceListView.Items.Add(deviceListViewItem);
            }
        }

        /// <summary>
        /// 将Device List中所记录设备显示至DeviceListView控件;
        /// </summary>
        private void ClearDeviceListView()
        {
            DevControl.tagErrorCode eCode;
            List<DeviceClass> deviceList = DevList;

            foreach (DeviceClass device in deviceList)
            {
                eCode = DevControl.DM_FreeDevice(device.DevHandle);
                Debug.Assert(eCode == DevControl.tagErrorCode.DM_ERR_OK);
            }
            //清空设备列表，并清空对应显示控件；
            DevList.Clear();
            ReflashDeviceListView(DevList);
        }

        /// <summary>
        /// 搜索设备，然后将记录搜索结果的DevList显示至DeviceListView控件;
        /// </summary>
        private bool SearchDevice(uint targetIP)
        {
            ClearDeviceListView();
            DevControl.tagErrorCode eCode = DevControl.DM_SearchDevice(targetIP, 1500);
            if (eCode == DevControl.tagErrorCode.DM_ERR_OK)
            {
                ReflashDeviceListView(DevList);
                return true;
            }
            else
            {
                //异常处理；
                string errMsg = ErrorHandling.HandleError(eCode);
                System.Windows.Forms.MessageBox.Show(errMsg);
                return false;
            }
        }

        /// <summary>
        /// 配置选定设备，开启对应配置窗体;
        /// </summary>
        private void ConfigSelectedDevice()
        {
            if (this.DeviceListView.SelectedIndices.Count > 0
                && this.DeviceListView.SelectedIndices[0] != -1)
            {
                //通过用户在显示控件中选择的索引值，在查找其所对应的设备对象；
                DeviceClass currentDevice = DevList[DeviceListView.SelectedIndices[0]];

                LoginForm loginform = new LoginForm();
                DialogResult result = loginform.ShowDialog();
                if (result == DialogResult.OK)
                {
                    DevControl.tagErrorCode eCode = currentDevice.Login(loginform.UserName, loginform.Password);
                    if (eCode == DevControl.tagErrorCode.DM_ERR_OK)
                    {
                        //记录当前选择设备对象，作为父窗体属性传递至新开启的子配置窗体；
                        this.SelectedDevice = currentDevice;
                        ConfigForm deviceConfigForm = new ConfigForm(this.SelectedDevice);
                        deviceConfigForm.ShowDialog(this);
                        deviceConfigForm.Dispose();
                    }
                    else
                    {
                        //异常处理；
                        string errMsg = ErrorHandling.HandleError(eCode);
                        System.Windows.Forms.MessageBox.Show(errMsg);
                    }
                }

                loginform.Dispose();
            }
        }
        private void searchToolStripMenuItem_Click(object sender, EventArgs e)
        {
            //使用广播搜索设备；
            SearchDevice(DeviceClass.Broadcast);
        }

        private void configToolStripMenuItem_Click(object sender, EventArgs e)
        {
            ConfigSelectedDevice();
        }

        private void clearToolStripMenuItem_Click(object sender, EventArgs e)
        {
            ClearDeviceListView();
        }

        private void exitToolStripMenuItem_Click(object sender, EventArgs e)
        {
            //关闭主窗体并退出程序；
            this.Close();
        }

        private void iEToolStripMenuItem_Click(object sender, EventArgs e)
        {
            //开启IE访问目标设备；
            try
            {
                if (DeviceListView.SelectedIndices.Count > 0
                    && DeviceListView.SelectedIndices[0] != -1)
                {
                    DeviceClass currentDevice = DevList[DeviceListView.SelectedIndices[0]];
                    System.Diagnostics.Process.Start("iexplore.exe", "HTTP://" + getIPAddress(currentDevice.DeviceIP).ToString());
                }
            }
            catch (Exception ex)
            {
                Log.WriteException(ex);
            }
        }

        private void telnetToolStripMenuItem_Click(object sender, EventArgs e)
        {
            //开启TELNET客户端访问目标设备；
            try
            {
                if (DeviceListView.SelectedIndices.Count > 0
                    && DeviceListView.SelectedIndices[0] != -1)
                {
                    DeviceClass currentDevice = DevList[DeviceListView.SelectedIndices[0]];
                    System.Diagnostics.Process.Start("telnet.exe", getIPAddress(currentDevice.DeviceIP).ToString());
                }
            }
            catch (Exception ex)
            {
                Log.WriteException(ex);
            }
        }

        private void pingToolStripMenuItem_Click(object sender, EventArgs e)
        {
            try
            {
                if (DeviceListView.SelectedIndices.Count > 0
                    && DeviceListView.SelectedIndices[0] != -1)
                {
                    DeviceClass currentDevice = DevList[DeviceListView.SelectedIndices[0]];
                    System.Diagnostics.Process.Start("ping.exe", getIPAddress(currentDevice.DeviceIP).ToString() + " -t");
                }
            }
            catch (Exception ex)
            {
                Log.WriteException(ex);
            }
        }

        private void Form1_FormClosed(object sender, FormClosedEventArgs e)
        {
            DevControl.tagErrorCode eCode = DevControl.DM_DeInit();
            if (eCode != DevControl.tagErrorCode.DM_ERR_OK)
            {
                ErrorHandling.HandleError(eCode);
            }
        }

        private void DeviceListView_DoubleClick(object sender, EventArgs e)
        {
            ConfigSelectedDevice();
        }

        private void btFlashROM_Click(object sender, EventArgs e)
        {
            if (MessageBox.Show(this, "Changed to Update Rom mode,if want to restore,need turn off and turn on power,are you sure do that?", "information", MessageBoxButtons.OKCancel) == DialogResult.Cancel)
                return;
            fCmdRet = RWDev.SetFlashRom(ref fComAdr, frmcomportindex);
            if (fCmdRet != 0)
            {
                string strLog = "Change mode failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Change mode success ";
                WriteLog(lrtxtLog, strLog, 0);
                if (frmcomportindex > 0 && frmcomportindex<256)
                {
                    btDisConnect232_Click(null,null);
                }
            }
        }
        public class ctcplist//存储100客户端信息.
        {
            public Socket[] tempSocket = new Socket[100];
            public string[] ip = new string[100];
            public int[] port = new int[100];
        }
        ctcplist tcplist = new ctcplist();
        Thread listenThread = null;//监听进程
        Socket newsock = null;
        private void StartListening() //main listening thread
        {
            int port = Convert.ToInt32(stcpport.Text);
            IPEndPoint ipep = new IPEndPoint(IPAddress.Any, port);//绑定端口
            newsock = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);//tcp协议
            newsock.Bind(ipep);
            newsock.Listen(10);
            while (true)
            {
                try
                {
                    Socket client = newsock.Accept();//等待TCP客户端的链接请求
                    //查找空缺，插入信息
                    int m = 0;
                    for (m = 0; m < 100; m++)
                    {
                        if (tcplist.ip[m] == null)
                        {
                            int nport = ((System.Net.IPEndPoint)client.RemoteEndPoint).Port;
                            IPAddress ip = ((System.Net.IPEndPoint)client.RemoteEndPoint).Address;
                            tcplist.tempSocket[m] = client;
                            tcplist.ip[m] = ip.ToString();
                            tcplist.port[m] = nport;
                            this.Invoke((EventHandler)delegate
                            {
                                listtcp.Items.Add(ip.ToString() + ":" + nport.ToString());
                            });

                            break;
                        }
                    }
                    ParameterizedThreadStart ParStart = new ParameterizedThreadStart(ServiceClient);
                    Thread clientService = new Thread(ParStart);
                    clientService.IsBackground = true;
                    object o = client;
                    clientService.Start(o);
                }
                catch (System.Exception ex)
                {
                    break;
                }
            }
        }
        private void btListen_Click(object sender, EventArgs e)
        {
            //创建监听进程
            stcpport.Enabled = false;
            btListen.Enabled = false;
            listenThread = new Thread(new ThreadStart(StartListening));
            listenThread.IsBackground = true;
            listenThread.Start();
        }
        public static string ByteArrayToHexString2(byte[] data)
        {
            StringBuilder sb = new StringBuilder(data.Length * 3);
            foreach (byte b in data)
                sb.Append(Convert.ToString(b, 16).PadLeft(2, '0').PadLeft(3, ' '));
            return sb.ToString().ToUpper();

        }
        public void ServiceClient(object ParObject)
        {
            Socket tempSocket = (Socket)ParObject;
            IPEndPoint newclient = (IPEndPoint)tempSocket.RemoteEndPoint;

          //  NetworkStream ns = new NetworkStream(tempSocket);
         //   StreamReader sr = new StreamReader(ns);
            byte[] myReadBuffer = new byte[1024];
            IPAddress ip = (newclient).Address;
            int nport = (newclient).Port;
            int count = 0;
            string temp = "";
            while (true)
            {
                try
                {
                    count = tempSocket.Receive(myReadBuffer);
                    if (count > 0)
                    {
                        byte[] data = new byte[count];
                        Array.Copy(myReadBuffer, data, count);
                        temp = ByteArrayToHexString2(data);
                        this.Invoke((EventHandler)delegate
                        {
                            stcprecv.AppendText(Environment.NewLine + ip.ToString() + ":" + nport.ToString() + " " + temp);
                            stcprecv.Select(stcprecv.TextLength, 0);
                            stcprecv.ScrollToCaret();
                        });
                    }
                    else
                    {
                        this.Invoke((EventHandler)delegate
                        {
                            int m = 0;
                            for (m = 0; m < 100; m++)
                            {
                                if (tcplist.ip[m] == ip.ToString() && (tcplist.port[m] == nport))//找到
                                {
                                    int n = listtcp.Items.IndexOf(ip.ToString() + ":" + nport.ToString());
                                    listtcp.Items.RemoveAt(n);
                                    tcplist.tempSocket[m].Close();
                                    tcplist.ip[m] = null;
                                    tcplist.port[m] = 0;
                                    tcplist.tempSocket[m] = null;
                                    break;
                                }
                            }
                        });
                        break;
                    }
                }
                catch
                {
                    //查找断开连接的设备IP
                    this.Invoke((EventHandler)delegate
                    {
                        int m = 0;
                        for (m = 0; m < 100; m++)
                        {
                            if (tcplist.ip[m] == ip.ToString() && (tcplist.port[m] == nport))//找到
                            {
                                int n = listtcp.Items.IndexOf(ip.ToString() + ":" + nport.ToString());
                                listtcp.Items.RemoveAt(n);
                                tcplist.tempSocket[m].Close();
                                tcplist.ip[m] = null;
                                tcplist.port[m] = 0;
                                tcplist.tempSocket[m] = null;
                                break;
                            }
                        }
                    });
                    break;
                }
            }
        }

        private void btStop_Click(object sender, EventArgs e)
        {
            int m = 0;
            for (m = 0; m < 100; m++)
            {
                if (tcplist.tempSocket[m] != null)//找到
                {

                    int n = listtcp.Items.IndexOf(tcplist.ip[m] + ":" + tcplist.port[m].ToString());
                    listtcp.Items.RemoveAt(n);
                    tcplist.tempSocket[m].Close();
                    tcplist.ip[m] = null;
                    tcplist.port[m] = 0;
                    tcplist.tempSocket[m] = null;
                }
            }

            if (newsock != null)
                newsock.Close();
            if (listenThread != null)
                listenThread.Abort();

            stcpport.Enabled = true;
            btListen.Enabled = true;
        }
        Socket m_client;
        Thread clientThread = null;

        private void bttcpconnect_Click(object sender, EventArgs e)
        {
            try
            {
                string ip = tcpremoteIp.IpAddressStr;
                int nipport = Convert.ToInt32(remotePort.Text);
                m_client = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                IPEndPoint ie = new IPEndPoint(IPAddress.Parse(ip), nipport);
                m_client.Connect(ie);
                if (m_client.Connected)
                {
                    tcpremoteIp.Enabled = false;
                    remotePort.Enabled = false;
                    bttcpconnect.Enabled = false;//连接成功创建接收数据线程
                    bttcpsend.Enabled = true;
                    clientThread = new Thread(new ThreadStart(StartRead));
                    clientThread.IsBackground = true;
                    clientThread.Start();
                }
                else
                {
                    tcpremoteIp.Enabled = true;
                    remotePort.Enabled = true;
                    bttcpconnect.Enabled = true;
                    bttcpsend.Enabled = false;
                }

            }
            catch (SocketException ex)
            {
                tcpremoteIp.Enabled = true;
                remotePort.Enabled = true;
                bttcpconnect.Enabled = true;
                bttcpsend.Enabled = false;
            }
        }//接收数据线程

        private void StartRead()
        {
            byte[] buffs = new byte[2048];
            IPEndPoint newclient = (IPEndPoint)m_client.RemoteEndPoint;
            IPAddress ip = (newclient).Address;
            int nport = (newclient).Port;
            while (true)
            {
                try
                {
                    int count = m_client.Receive(buffs);
                    if (count > 0)
                    {
                        byte[] data = new byte[count];
                        Array.Copy(buffs, data, count);
                        string temp = ByteArrayToHexString2(data);
                        this.Invoke((EventHandler)delegate
                        {
                            ctctrecv.AppendText(Environment.NewLine + ip.ToString() + ":" + nport.ToString() + " " + temp);
                            ctctrecv.Select(stcprecv.TextLength, 0);
                            ctctrecv.ScrollToCaret();
                        });

                    }
                }
                catch (System.Exception ex)
                {
                    if (m_client.Connected)
                    {
                        m_client.Shutdown(SocketShutdown.Both);
                        m_client.Close();
                    }
                    this.Invoke((EventHandler)delegate
                    {
                        tcpremoteIp.Enabled = true;
                        remotePort.Enabled = true;
                        bttcpconnect.Enabled = true;
                    });
                    break;
                }
            }
        }

        private void bttcpsend_Click(object sender, EventArgs e)
        {
            if (m_client.Connected)
            {
                string temp = ctctsend.Text.Replace(" ", "");
                if (temp == "") return;
                if (temp.Length % 2 != 0)
                    temp = temp + "0";
                byte[] buff = new byte[1024];
                buff = HexStringToByteArray(temp);
                int m = m_client.Send(buff);
            }
        }

        private void bttcpdisconnect_Click(object sender, EventArgs e)
        {
            if (m_client.Connected)
            {
                m_client.Shutdown(SocketShutdown.Both);
                m_client.Close();
                clientThread.Abort();
                tcpremoteIp.Enabled = true;
                remotePort.Enabled = true;
                bttcpconnect.Enabled = true;
                bttcpsend.Enabled = false;
            }
        }

        private void com_S_SelectedIndexChanged(object sender, EventArgs e)
        {
            if (com_S.SelectedIndex > 1)
            {
                check_num.Enabled = true;
                text_target.Enabled = true;
            }
            else
            {
                check_num.Enabled = false;
                text_target.Enabled = false;
            }
        }

        private void btExtRead_Click(object sender, EventArgs e)
        {
            byte ENum;
            byte Num = 0;
            byte Mem = 0;
            byte[] WordPtr=new byte[2];
            string str = ""; ;
            byte[] CardData = new byte[320];
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            text_WriteData.Text = "";
            if (checkBox1.Checked)
            {
                if ((maskadr_textbox.Text == "") || (maskLen_textBox.Text == "") || (maskData_textBox.Text == ""))
                {
                    return;
                }
                ENum = 255;
                if (R_EPC.Checked) MaskMem = 1;
                if (R_TID.Checked) MaskMem = 2;
                if (R_User.Checked) MaskMem = 3;
                MaskAdr = HexStringToByteArray(maskadr_textbox.Text);
                MaskLen = Convert.ToByte(maskLen_textBox.Text, 16);
                MaskData = HexStringToByteArray(maskData_textBox.Text);
            }
            else
            {
                if (check_selecttag.Checked)
                    str = text_epc.Text;
                else
                    str = "";
                ENum = Convert.ToByte(str.Length / 4);
            }
            byte[] EPC = new byte[ENum * 2];
            EPC = HexStringToByteArray(str);
            if (C_Reserve.Checked)
                Mem = 0;
            if (C_EPC.Checked)
                Mem = 1;
            if (C_TID.Checked)
                Mem = 2;
            if (C_User.Checked)
                Mem = 3;
            if (text_WordPtr.Text == "" || text_RWlen.Text == "" || text_AccessCode2.Text.Length != 8)
            {
                return;
            }
            WordPtr = HexStringToByteArray(text_WordPtr.Text);
            Num = Convert.ToByte(text_RWlen.Text);
            fPassWord = HexStringToByteArray(text_AccessCode2.Text);
            for (int p = 0; p < 10; p++)
            {
                fCmdRet = RWDev.ExtReadData_G2(ref fComAdr, EPC, ENum, Mem, WordPtr, Num, fPassWord, MaskMem, MaskAdr, MaskLen, MaskData, CardData, ref ferrorcode, frmcomportindex);
                if (fCmdRet == 0) break;
            }
            if (fCmdRet != 0)
            {
                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Extension Read data failed: " + "tag return error =0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Extension Read data failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                byte[] daw = new byte[Num * 2];
                Array.Copy(CardData, daw, Num * 2);
                text_WriteData.Text = ByteArrayToHexString(daw);
                string strLog = "Extension Read data success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btExtWrite_Click(object sender, EventArgs e)
        {
            byte ENum;
            byte WNum = 0;
            byte Mem = 0;
            byte[] WordPtr=new byte[2];
            string str = ""; 
            byte[] CardData = new byte[320];
            byte MaskMem = 0;
            byte[] MaskAdr = new byte[2];
            byte MaskLen = 0;
            byte[] MaskData = new byte[100];
            if (checkBox1.Checked)
            {
                if ((maskadr_textbox.Text == "") || (maskLen_textBox.Text == "") || (maskData_textBox.Text == ""))
                {
                    return;
                }
                ENum = 255;
                if (R_EPC.Checked) MaskMem = 1;
                if (R_TID.Checked) MaskMem = 2;
                if (R_User.Checked) MaskMem = 3;
                MaskAdr = HexStringToByteArray(maskadr_textbox.Text);
                MaskLen = Convert.ToByte(maskLen_textBox.Text, 16);
                MaskData = HexStringToByteArray(maskData_textBox.Text);
            }
            else
            {
                if (check_selecttag.Checked)
                    str = text_epc.Text;
                else
                    str = "";
                ENum = Convert.ToByte(str.Length / 4);
            }
            byte[] EPC = new byte[ENum * 2];
            EPC = HexStringToByteArray(str);
            if (C_Reserve.Checked)
                Mem = 0;
            if (C_EPC.Checked)
                Mem = 1;
            if (C_TID.Checked)
                Mem = 2;
            if (C_User.Checked)
                Mem = 3;
            if (text_WordPtr.Text == "" || text_AccessCode2.Text.Length != 8)
            {
                return;
            }
            string epcstr = text_WriteData.Text;
            if (epcstr.Length % 4 != 0 || epcstr.Length == 0)
            {
                MessageBox.Show("Input data by word.", "Information");
                return;
            }
            WNum = Convert.ToByte(epcstr.Length / 4);
            byte[] Writedata = new byte[WNum * 2 + 1];
            Writedata = HexStringToByteArray(epcstr);
            WordPtr = HexStringToByteArray(text_WordPtr.Text);
            fPassWord = HexStringToByteArray(text_AccessCode2.Text);
            if ((checkBox_pc.Checked) && (C_EPC.Checked))
            {
                WordPtr = HexStringToByteArray("0001");
                WNum = Convert.ToByte(epcstr.Length / 4 + 1);
                Writedata = HexStringToByteArray(textBox_pc.Text + epcstr);
            }
            for (int p = 0; p < 10; p++)
            {
                fCmdRet = RWDev.ExtWriteData_G2(ref fComAdr, EPC, WNum, ENum, Mem, WordPtr, Writedata, fPassWord, MaskMem, MaskAdr, MaskLen, MaskData, ref ferrorcode, frmcomportindex);
                if (fCmdRet == 0) break;
            }
            if (fCmdRet != 0)
            {
                string strLog = "";
                if (fCmdRet == 0xFC)
                    strLog = "Extension Write data failed: " + "tag return error=0x" + Convert.ToString(ferrorcode, 16) + "(" + GetErrorCodeDesc(ferrorcode) + ")";
                else
                    strLog = "Extension Write data failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 1);
            }
            else
            {
                string strLog = "Extension Write data success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btSetEPCandTIDLen_Click(object sender, EventArgs e)
        {
            byte SaveLen = 0;
            if (rb128.Checked)
            {
                SaveLen = 0;
            }
            else
            {
                SaveLen = 1;
            }
            fCmdRet = RWDev.SetSaveLen(ref fComAdr, SaveLen, frmcomportindex);
            if (fCmdRet == 0)
            {
                string strLog = "Set buffer EPC/TID length success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
            else
            {
                string strLog = "Set buffer EPC/TID length failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btGetEPCandTIDLen_Click(object sender, EventArgs e)
        {
            byte SaveLen = 0;
            fCmdRet = RWDev.GetSaveLen(ref fComAdr, ref SaveLen, frmcomportindex);
            if (fCmdRet == 0)
            {
                if (SaveLen == 0)
                    rb128.Checked = true;
                else
                    rb496.Checked = true;
                string strLog = "Get buffer EPC/TID length success";
                WriteLog(lrtxtLog, strLog, 0);
            }
            else
            {
                string strLog = "Get buffer EPC/TID length failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btStartBuff_Click(object sender, EventArgs e)
        {
            timer_runmode.Enabled = !timer_runmode.Enabled;
            if (!timer_runmode.Enabled)
            {
                btStartBuff.Text = "Start";
                btStartBuff.BackColor = Color.Transparent;
            }
            else
            {
                fInventory_EPC_List = "";
                if (rb_bepc.Checked)
                    TIDFlag = 0;
                else
                    TIDFlag = 1;
                total_time = System.Environment.TickCount;
                total_tagnum = 0;
                dataGridView2.Rows.Clear();
                btStartBuff.BackColor = Color.Indigo;
                fIsInventoryScan = false;
                btStartBuff.Text = "Stop";
            }
        }

        private void btReadBuff_Click(object sender, EventArgs e)
        {
            int Totallen = 0;
            int CardNum = 0;
            byte[] pEPCList = new byte[30000];
            lxLed_Num.Text = "0";
            lxLed_cmdsud.Text = "0";
            lxLed_toltag.Text = "0";
            lxLed_toltime.Text = "0";
            lxLed_cmdTime.Text = "0";
            dataGridView2.Rows.Clear();
            string temp = "";
            fCmdRet = RWDev.ReadBuffer_G2(ref fComAdr, ref Totallen, ref CardNum, pEPCList, frmcomportindex);
            if (fCmdRet == 1)
            {
                int m = 0;
                byte[] daw = new byte[Totallen];
                Array.Copy(pEPCList, daw, Totallen);
                for (int i = 0; i < CardNum; i++)
                {
                    string ant = Convert.ToString(daw[m], 2).PadLeft(4, '0');
                    int len = daw[m + 1];
                    byte[] EPC = new byte[len];
                    Array.Copy(daw, m + 2, EPC, 0, len);
                    string sEPC = ByteArrayToHexString(EPC);
                    string RSSI = daw[m + 2 + len].ToString();
                    string sCount = daw[m + 3 + len].ToString();
                    m = m + 4 + len;
                    string[] arr = new string[6];
                    arr[0] = (dataGridView2.RowCount + 1).ToString();
                    arr[1] = sEPC;
                    arr[2] = len.ToString();
                    arr[3] = ant;
                    arr[4] = RSSI;
                    arr[5] = sCount;
                    dataGridView2.Rows.Insert(dataGridView2.RowCount, arr);
                }
                lxLed_Num.Text = dataGridView2.RowCount.ToString();
                string strLog = "Read buffer over ";
                WriteLog(lrtxtLog, strLog, 0);
            }
            else
            {
                lxLed_Num.Text = "0";
                string strLog = "Read buffer failed";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btClearBuff_Click(object sender, EventArgs e)
        {
            fCmdRet = RWDev.ClearBuffer_G2(ref fComAdr, frmcomportindex);
            if (fCmdRet == 0)
            {
                string strLog = "Clear buffer success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
            else
            {
                string strLog = "Clear buffer failed";
                WriteLog(lrtxtLog, strLog, 0);
            }
        }

        private void btRandCbuff_Click(object sender, EventArgs e)
        {
            btReadBuff_Click(null,null);
            btClearBuff_Click(null,null);
        }

        private void btQueryBuffNum_Click(object sender, EventArgs e)
        {
            int Count = 0;
            lxLed_cmdsud.Text = "0";
            lxLed_cmdTime.Text = "0";
            lxLed_Num.Text = "0";
            lxLed_toltag.Text = "0";
            lxLed_toltime.Text = "0";
            fCmdRet = RWDev.GetBufferCnt_G2(ref fComAdr, ref Count, frmcomportindex);
            if (fCmdRet == 0)
            {
                lxLed_Num.Text = Count.ToString();
                string strLog = "Get buffer tag number success ";
                WriteLog(lrtxtLog, strLog, 0);
            }
            else
            {
                string strLog = "Get buffer tag number failed: " + GetReturnCodeDesc(fCmdRet);
                WriteLog(lrtxtLog, strLog, 0);
            }
        }



    }
}
