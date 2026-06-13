unit frmRRU9816demomain;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs,fProgressbar, StdCtrls, ComCtrls,RRU9816_Head,RRU9816_DLL_Head,
  ActnList, Buttons, ExtCtrls, Menus,WinSock,shellapi,
  ToolWin;

type
  TfrmRRU9816main = class(TForm)
    PageControl1: TPageControl;
    TabSheet1: TTabSheet;
    TabSheet_EPCC1G2: TTabSheet;
    StatusBar1: TStatusBar;
    GroupBox_ReaderInfo: TGroupBox;
    Label2: TLabel;
    Label3: TLabel;
    Label4: TLabel;
    Label10: TLabel;
    Label11: TLabel;
    Label8: TLabel;
    Label13: TLabel;
    Label14: TLabel;
    Edit_Version: TEdit;
    Edit_ComAdr: TEdit;
    Edit_scantime: TEdit;
    Edit_Type: TEdit;
    Button3: TButton;
    Edit_dmaxfre: TEdit;
    Edit_dminfre: TEdit;
    Edit_power: TEdit;
    EPCC1G2: TCheckBox;
    GroupBox2: TGroupBox;
    Label15: TLabel;
    Label16: TLabel;
    Label17: TLabel;
    Label1: TLabel;
    Label7: TLabel;
    Label5: TLabel;
    Button5: TButton;
    ComboBox_baud: TComboBox;
    Edit_NewComAdr: TEdit;
    ComboBox_scantime: TComboBox;
    Button1: TButton;
    ComboBox_dminfre: TComboBox;
    ComboBox_dmaxfre: TComboBox;
    ComboBox_PowerDbm: TComboBox;
    CheckBox_SameFre: TCheckBox;
    GroupBox7: TGroupBox;
    RadioButton_band2: TRadioButton;
    RadioButton_band3: TRadioButton;
    RadioButton_band4: TRadioButton;
    RadioButton_band5: TRadioButton;
    ActionList1: TActionList;
    Action_GetReaderInformation: TAction;
    Action_OpenCOM: TAction;
    Action_OpenRf: TAction;
    Action_CloseCOM: TAction;
    Action_CloseRf: TAction;
    Action_WriteComAdr: TAction;
    Action_WriteInventoryScanTime: TAction;
    Action_OpenTestMode: TAction;
    Action_CloseTestMode: TAction;
    Action_GetSystemInformation: TAction;
    Action_SetReaderInformation: TAction;
    Action_SetReaderInformation_0: TAction;
    Action_Inventory: TAction;
    Action_ShowOrChangeData: TAction;
    Action_SetProtectState: TAction;
    Action_DestroyCard: TAction;
    Action_SelfTestMode: TAction;
    Action_SelfTestMode2: TAction;
    Action_RfOutput: TAction;
    Action_RfOutput2: TAction;
    Action_SetDAC: TAction;
    Action_GetDAC: TAction;
    Action_SetPowerParameter: TAction;
    Action_SolidifyPower: TAction;
    Action_CheckPowerParameter: TAction;
    Action_GetStartInformation: TAction;
    Action_ReadPowerParameter: TAction;
    Action_Inventroy_6B: TAction;
    Action_Query_6B: TAction;
    Action_WriteData_6B: TAction;
    Action_ReadData_6B: TAction;
    Action_LockByte_6B: TAction;
    Action_CheckLock_6B: TAction;
    Action_Query2_6B: TAction;
    Action_ShowOrChangeData_BlockErase: TAction;
    Action_SetReadProtect_G2: TAction;
    Action_RemoveReadProtect_G2: TAction;
    Action_SetMultiReadProtect_G2: TAction;
    Action_CheckReadProtected_G2: TAction;
    Action_SetEASAlarm_G2: TAction;
    Action_CheckEASAlarm_G2: TAction;
    Action_LockUserBlock_G2: TAction;
    Action_WriteEPC_G2: TAction;
    Action_WriteList: TAction;
    Action_SolidifyPWMandPowerlist: TAction;
    Action_DeleteRfOutput: TAction;
    GroupBox11: TGroupBox;
    ListView_EPC: TListView;
    GroupBox17: TGroupBox;
    Label25: TLabel;
    SpeedButton_Query: TSpeedButton;
    ComboBox_IntervalTime: TComboBox;
    GroupBox9: TGroupBox;
    Label33: TLabel;
    Button_DestroyCard: TButton;
    Edit_DestroyCode: TEdit;
    ComboBox_EPC3: TComboBox;
    GroupBox23: TGroupBox;
    Label38: TLabel;
    Label39: TLabel;
    Edit_AccessCode3: TEdit;
    Button_WriteEPC_G2: TButton;
    Edit_WriteEPC: TEdit;
    GroupBox20: TGroupBox;
    Label32: TLabel;
    ComboBox_EPC4: TComboBox;
    Edit_AccessCode4: TEdit;
    Button_SetReadProtect_G2: TButton;
    Button_SetMultiReadProtect_G2: TButton;
    Button_RemoveReadProtect_G2: TButton;
    Button_CheckReadProtected_G2: TButton;
    GroupBox21: TGroupBox;
    Label35: TLabel;
    SpeedButton_CheckAlarm_G2: TSpeedButton;
    Label_Alarm: TLabel;
    Button_SetEASAlarm_G2: TButton;
    ComboBox_EPC5: TComboBox;
    Edit_AccessCode5: TEdit;
    GroupBox24: TGroupBox;
    Alarm_G2: TRadioButton;
    NoAlarm_G2: TRadioButton;
    GroupBox22: TGroupBox;
    Label36: TLabel;
    Label37: TLabel;
    Button_LockUserBlock_G2: TButton;
    ComboBox_BlockNum: TComboBox;
    ComboBox_EPC6: TComboBox;
    Edit_AccessCode6: TEdit;
    GroupBox5: TGroupBox;
    Label24: TLabel;
    ComboBox_EPC1: TComboBox;
    Button_SetProtectState: TButton;
    Edit_AccessCode1: TEdit;
    GroupBox1: TGroupBox;
    P_Reserve: TRadioButton;
    P_EPC: TRadioButton;
    P_TID: TRadioButton;
    P_User: TRadioButton;
    GroupBox16: TGroupBox;
    GroupBox4: TGroupBox;
    DestroyCode: TRadioButton;
    AccessCode: TRadioButton;
    NoProect: TRadioButton;
    Always: TRadioButton;
    Proect: TRadioButton;
    AlwaysNot: TRadioButton;
    GroupBox18: TGroupBox;
    NoProect2: TRadioButton;
    AlwaysNot2: TRadioButton;
    Proect2: TRadioButton;
    Always2: TRadioButton;
    GroupBox10: TGroupBox;
    Label9: TLabel;
    Label18: TLabel;
    Label19: TLabel;
    Label20: TLabel;
    SpeedButton_Read_G2: TSpeedButton;
    ComboBox_EPC2: TComboBox;
    Edit_AccessCode2: TEdit;
    Edit_WriteData: TEdit;
    Edit_WordPtr: TEdit;
    Edit_Len: TEdit;
    Memo_DataShow: TMemo;
    GroupBox6: TGroupBox;
    C_Reserve: TRadioButton;
    C_EPC: TRadioButton;
    C_TID: TRadioButton;
    C_User: TRadioButton;
    Button16: TButton;
    Button_DataWrite: TButton;
    Button_BlockErase: TButton;
    Timer_Test_: TTimer;
    Timer_G2_Read: TTimer;
    Button_BlockWrite: TButton;
    Action_ShowOrChangeData_write: TAction;
    Action_ShowOrChangeData_BlockWrite: TAction;
    Timer_G2_Alarm: TTimer;
    Timer1: TTimer;
    Timer_Test_6B: TTimer;
    Timer_6B_ReadWrite: TTimer;
    Action_TagProtocol: TAction;
    TabSheet3: TTabSheet;
    Label62: TLabel;
    Label63: TLabel;
    Label64: TLabel;
    ListBox1: TListBox;
    Button21: TButton;
    Button23: TButton;
    Button24: TButton;
    GroupBox8: TGroupBox;
    Radio_beepEn: TRadioButton;
    Radio_beepDis: TRadioButton;
    Button_Beep: TButton;
    GroupBox27: TGroupBox;
    Button_SetGPIO: TButton;
    Button_GetGPIO: TButton;
    CheckBox2: TCheckBox;
    CheckBox3: TCheckBox;
    CheckBox6: TCheckBox;
    GroupBox30: TGroupBox;
    GroupBox_COM: TGroupBox;
    Label6: TLabel;
    Label12: TLabel;
    Label47: TLabel;
    ComboBox_COM: TComboBox;
    Button2: TButton;
    Button4: TButton;
    StaticText1: TStaticText;
    Edit_CmdComAddr: TEdit;
    ComboBox_AlreadyOpenCOM: TComboBox;
    ComboBox_baud2: TComboBox;
    MainMenu1: TMainMenu;
    Operation1: TMenuItem;
    tools1: TMenuItem;
    Search1: TMenuItem;
    clear1: TMenuItem;
    xxit1: TMenuItem;
    IE1: TMenuItem;
    elnet1: TMenuItem;
    Ping1: TMenuItem;
    Language1: TMenuItem;
    Help1: TMenuItem;
    About1: TMenuItem;
    English1: TMenuItem;
    GroupBox44: TGroupBox;
    Label67: TLabel;
    Label68: TLabel;
    Edit13: TEdit;
    Edit14: TEdit;
    Edit_PC: TEdit;
    CheckBox18: TCheckBox;
    GroupBox45: TGroupBox;
    Edit15: TEdit;
    Button8: TButton;
    Label89: TLabel;
    Edit17: TEdit;
    Label90: TLabel;
    Edit18: TEdit;
    GroupBox13: TGroupBox;
    Label27: TLabel;
    Label28: TLabel;
    Label21: TLabel;
    CheckBox1: TCheckBox;
    Edit2: TEdit;
    Edit3: TEdit;
    GroupBox3: TGroupBox;
    R_EPC: TRadioButton;
    R_TID: TRadioButton;
    R_User: TRadioButton;
    Edit1: TEdit;
    CheckBox_TID: TCheckBox;
    Label29: TLabel;
    Com_Q: TComboBox;
    Label30: TLabel;
    Com_S: TComboBox;
    TabSheet_6B: TTabSheet;
    GroupBox14: TGroupBox;
    GroupBox19: TGroupBox;
    Label31: TLabel;
    ComboBox_IntervalTime_6B: TComboBox;
    Byone_6B: TRadioButton;
    Bycondition_6B: TRadioButton;
    GroupBox32: TGroupBox;
    Label34: TLabel;
    Label42: TLabel;
    Label43: TLabel;
    SpeedButton_Read_6B: TSpeedButton;
    SpeedButton_Write_6B: TSpeedButton;
    ComboBox_ID1_6B: TComboBox;
    Edit_WriteData_6B: TEdit;
    Edit_StartAddress_6B: TEdit;
    Edit_Len_6B: TEdit;
    Memo_DataShow_6B: TMemo;
    Button7: TButton;
    Button10: TButton;
    Button11: TButton;
    GroupBox33: TGroupBox;
    Label51: TLabel;
    Label52: TLabel;
    Edit_Query_StartAddress_6B: TEdit;
    Edit_ConditionContent_6B: TEdit;
    Less_6B: TRadioButton;
    Different_6B: TRadioButton;
    Same_6B: TRadioButton;
    Greater_6B: TRadioButton;
    ListView_ID_6B: TListView;
    SpeedButton_Query_6B: TSpeedButton;
    ISO180006B: TCheckBox;
    Label22: TLabel;
    ComboBox1: TComboBox;
    CheckBox4: TCheckBox;
    TabSheet2: TTabSheet;
    GroupBox12: TGroupBox;
    rb_128: TRadioButton;
    rb_496: TRadioButton;
    bt_setlen: TButton;
    bt_getlen: TButton;
    GroupBox15: TGroupBox;
    btStartBuffer: TButton;
    rb_BEPC: TRadioButton;
    rb_BTID: TRadioButton;
    GroupBox25: TGroupBox;
    Label23: TLabel;
    lb_Num: TLabel;
    GroupBox26: TGroupBox;
    btGetBuffer: TButton;
    btGetAndClBuffer: TButton;
    btClearBuffer: TButton;
    btGetBufferNum: TButton;
    Label26: TLabel;
    btClear: TButton;
    ListView1: TListView;
    ExtRead: TButton;
    ExtWrite: TButton;
    procedure FormCreate(Sender: TObject);
    procedure Button2Click(Sender: TObject);
    procedure Button4Click(Sender: TObject);
    procedure Action_GetReaderInformationExecute(Sender: TObject);
    procedure ComboBox_AlreadyOpenCOMCloseUp(Sender: TObject);
    procedure Action_SetReaderInformationExecute(Sender: TObject);
    procedure RadioButton_band2Click(Sender: TObject);
    procedure RadioButton_band3Click(Sender: TObject);
    procedure RadioButton_band4Click(Sender: TObject);
    procedure RadioButton_band5Click(Sender: TObject);
    procedure Action_GetReaderInformationUpdate(Sender: TObject);
    procedure CheckBox_SameFreClick(Sender: TObject);
    procedure Edit2KeyPress(Sender: TObject; var Key: Char);
    procedure SpeedButton_QueryClick(Sender: TObject);
    procedure Action_InventoryExecute(Sender: TObject);
    procedure Timer_Test_Timer(Sender: TObject);
    procedure ComboBox_IntervalTimeChange(Sender: TObject);
    procedure SpeedButton_Read_G2Click(Sender: TObject);
    procedure Timer_G2_ReadTimer(Sender: TObject);
    procedure Action_ShowOrChangeDataExecuteExecute(Sender: TObject);
    procedure Action_SetProtectStateExecute(Sender: TObject);
    procedure Action_SetProtectStateUpdate(Sender: TObject);
    procedure Action_DestroyCardExecute(Sender: TObject);
    procedure Action_WriteEPC_G2Execute(Sender: TObject);
    procedure Action_SetReadProtect_G2Execute(Sender: TObject);
    procedure Action_SetMultiReadProtect_G2Execute(Sender: TObject);
    procedure Action_RemoveReadProtect_G2Execute(Sender: TObject);
    procedure Action_CheckReadProtected_G2Execute(Sender: TObject);
    procedure Action_SetEASAlarm_G2Execute(Sender: TObject);
    procedure SpeedButton_CheckAlarm_G2Click(Sender: TObject);
    procedure Timer_G2_AlarmTimer(Sender: TObject);
    procedure Action_LockUserBlock_G2Execute(Sender: TObject);
    procedure PageControl1Change(Sender: TObject);
    procedure Button_BeepClick(Sender: TObject);
    procedure Edit8KeyPress(Sender: TObject; var Key: Char);
    procedure Button_clearBufferClick(Sender: TObject);
    procedure Button_SetGPIOClick(Sender: TObject);
    procedure Button_GetGPIOClick(Sender: TObject);
    procedure ComboBox_dminfreSelect(Sender: TObject);
    procedure Button16Click(Sender: TObject);
    procedure Button21Click(Sender: TObject);
    procedure Button23Click(Sender: TObject);
    procedure Button24Click(Sender: TObject);
    procedure ComboBox_COMChange(Sender: TObject);
    procedure xxit1Click(Sender: TObject);
    procedure FormCloseQuery(Sender: TObject; var CanClose: Boolean);
    procedure CheckBox_TIDClick(Sender: TObject);
    procedure Edit_WriteDataChange(Sender: TObject);
    procedure CheckBox18Click(Sender: TObject);
    procedure C_ReserveClick(Sender: TObject);
    procedure C_TIDClick(Sender: TObject);
    procedure C_UserClick(Sender: TObject);
    procedure C_EPCClick(Sender: TObject);
    procedure Button31Click(Sender: TObject);
    procedure Button34Click(Sender: TObject);
    procedure Button8Click(Sender: TObject);
    procedure Action_Inventroy_6BExecute(Sender: TObject);
    procedure Action_Query_6BExecute(Sender: TObject);
    procedure Action_LockByte_6BExecute(Sender: TObject);
    procedure Action_CheckLock_6BExecute(Sender: TObject);
    procedure Action_CheckLock_6BUpdate(Sender: TObject);
    procedure SpeedButton_Read_6BClick(Sender: TObject);
    procedure Button11Click(Sender: TObject);
    procedure ComboBox_IntervalTime_6BChange(Sender: TObject);
    procedure Timer_Test_6BTimer(Sender: TObject);
    procedure Timer_6B_ReadWriteTimer(Sender: TObject);
    procedure bt_setlenClick(Sender: TObject);
    procedure bt_getlenClick(Sender: TObject);
    procedure btStartBufferClick(Sender: TObject);
    procedure btGetBufferClick(Sender: TObject);
    procedure btClearBufferClick(Sender: TObject);
    procedure btGetAndClBufferClick(Sender: TObject);
    procedure btGetBufferNumClick(Sender: TObject);
    procedure Timer1Timer(Sender: TObject);
    procedure btClearClick(Sender: TObject);
    procedure ExtWriteClick(Sender: TObject);
    procedure ExtReadClick(Sender: TObject);
  private
    { Private declarations }
     fAppClosed: Boolean; //在测试模式下响应关闭应用程序
    fComAdr: Byte; //当前操作的ComAdr
    ComIsOpen:Boolean;
    ferrorcode:LongInt;
    fBaud:Byte;
    fdminfre:Real;
    fdmaxfre:Real;
    fCmdRet: LongInt; //所有执行指令的返回值
    fOpenComIndex: Integer; //打开的串口索引号
    ReaderType:Byte;
     x_z,y_f:Real;
    Suc_count:LongInt;
    Query_count:LongInt;
    card_Count:DWORD;
    fInventory_EPC_List: string; //存贮询查列表（如果读取的数据没有变化，则不进行刷新）
    fInventory_TID_List: string; //存贮询查列表（如果读取的数据没有变化，则不进行刷新）
    Istemps02Save: boolean;
    temps02Save: string; // 存储继续询查前上次已经询查到的卡
    fIsInventoryScan : Boolean;
    fTimer_G2_Read:Boolean;
    fTimer_G2_Alarm: Boolean;
    fisinventoryscan_6B:Boolean;
    fTimer_6B_ReadWrite:Boolean;
    ISscanstring:Boolean ;
    breakflag:Boolean;
    fOperEPC: array[0..35] of Char;
    fPassWord:array[0..4] of Char;
    fOperID_6B: array[0..8] of Char;
    fLogStrings:Tstrings;
    EnableFlag:Boolean;
    SeriaATflag:Boolean;
    Inant,FastFlag,ScanTime,Target:Byte;
    ReaderType_s:Byte;
    AA_times:LongInt;
  //  EPCstr_list:TStringList;
  public
    m_hDevArray:array[0..100]of LongInt;
    select_index:LongInt;
    function getStr(pStr: pchar; len: Integer): string;
    function getHexStr(sBinStr: string): string;
    procedure getCharStr(s:string;cStr: pchar);
    procedure InitComList;
    procedure InitReaderList;
    procedure RefreshStatus;
    procedure ClearLastInfo;
    procedure AddCmdLog(cmd, cmdName: string; cmdRet: Byte; errorCode: LongInt = -1);
    procedure AddCmdLog2(cmd, cmdName: string; cmdRet: Byte; CMDReturn:string;errorCode: LongInt = -1); //操作状态成功或错误提示函数
    function RoundClassic(R: Real): Int64;
    function getNoStr(no: Integer; noLen: Integer): string;
    Function Str_IntToBin(Int: LongInt; Size: Integer): String;
    function BitStrToHextStr(const BitStr: String): String;
    procedure SearchCallback1(var devIP:DWORD;mac, devName:PChar; dev:LongInt) ;
    { Public declarations }
  end;

var
  frmRRU9816main: TfrmRRU9816main;
  frmcomportindex:LongInt;

implementation

{$R *.dfm}


function TfrmRRU9816main.getStr(pStr: pchar; len: Integer): string;
var
  i: Integer;
begin
  result := '';
  for i := 0 to len - 1 do
    result := result + (pStr + i)^;
end;
function TfrmRRU9816main.getHexStr(sBinStr: string): string; //获得十六进制字符串
var
  i: Integer;
begin
  result := '';
  for i := 1 to Length(sBinStr) do
    result := result + IntToHex(ord(sBinStr[i]), 2);
end;

procedure TfrmRRU9816main.getCharStr(s:string;cStr: pchar); //获得字符串
var
  i: Integer;
begin
  try
    for i := 0 to Length(s) div 2-1 do
    (cStr+i)^ := Char(StrToInt('$' + copy(s, i * 2 + 1, 2)));
  except
  end;
end;

procedure TfrmRRU9816main.InitReaderList;
var
  i:Integer;
begin
  for i:=$03 to $ff do
  ComboBox_scantime.Items.Add(IntToStr(i)+'*100ms');
  ComboBox_scantime.ItemIndex := 7;

  for i:=$03 to $ff do
    ComboBox1.Items.Add(IntToStr(i)+'*100ms');
  ComboBox1.ItemIndex := 7;

  i:=10;
  while i<=1000 do
  begin
  ComboBox_IntervalTime.Items.Add(IntToStr(i)+'ms');
  i:=i+10;
  end;
  ComboBox_IntervalTime.ItemIndex :=0;
  for i:= 0 to 6 do
  ComboBox_BlockNum.Items.Add(IntToStr(i*2)+'and'+IntToStr(i*2+1));
  ComboBox_BlockNum.ItemIndex :=0;


   i:=40;
  while i<=300 do
  begin
  ComboBox_IntervalTime_6B.Items.Add(IntToStr(i)+'ms');
  i:=i+10;
  end;
  ComboBox_IntervalTime_6B.ItemIndex :=1;
end;
procedure TfrmRRU9816main.InitComList; //串口号初始化列表函数
var
  i: Integer;
begin
  ComboBox_COM.Items.Clear;
  ComboBox_COM.Items.Add(' AUTO');
  for i := 1 to 12 do
    ComboBox_COM.Items.Add(' COM' + IntToStr(i));
 // ComboBox_COM.Items.Add(' USB');
  ComboBox_COM.ItemIndex := 0;
  RefreshStatus;
end;
procedure TfrmRRU9816main.RefreshStatus; //通讯端口更新函数
begin
  if not (ComboBox_AlreadyOpenCOM.Items.Count <> 0) then
    StatusBar1.Panels.Items[1].Text := 'COM Closed'
  else
    StatusBar1.Panels.Items[1].Text := ' COM' + IntToStr(frmcomportindex);
  StatusBar1.Panels.Items[0].Text :='';
  StatusBar1.Panels.Items[2].Text :='';
end;
procedure TfrmRRU9816main.SearchCallback1(var devIP:DWORD;mac, devName:PChar; dev:LongInt ) ;
begin

end;

procedure TfrmRRU9816main.FormCreate(Sender: TObject);
begin
  fOpenComIndex := -1;
  fComAdr := 0;
  ferrorcode:= -1;
  fBaud:=5;
  InitComList;
  InitReaderList;
  ComboBox_baud2.ItemIndex:=3;
  RadioButton_band2.Checked:=True;
  ComboBox_PowerDbm.ItemIndex:=26;
  ComboBox_baud.ItemIndex:=3;
  R_EPC.Checked:=True;
  C_EPC.Checked:=True;
  P_EPC.Checked:=True;
  Radio_beepEn.Checked:=True;
  Istemps02Save := false;
  fAppClosed := False;
  Timer_Test_.Enabled := False;
  Timer_G2_Alarm.Enabled := False;
  Timer_G2_Read.Enabled := False;

  PageControl1.TabIndex:=0;
  fIsInventoryScan:=False;
  fisinventoryscan_6B:=False;
  ISscanstring:=False;
  AccessCode.Checked:=True;
  NoProect.Checked:=True;
  NoProect2.Checked:=True;
  Alarm_G2.Checked:=true;
  breakflag:=False;
  fLogStrings := TStringList.Create;
  EnableFlag:=False;
  FillChar(m_hDevArray,100,0);
  Com_Q.ItemIndex:=1;
  Com_S.ItemIndex:=0;
end;

procedure TfrmRRU9816main.Button2Click(Sender: TObject);
var
  port,i: LongInt;
  openresult :byte;
begin
  Screen.Cursor := crHourGlass;
  if  Edit_CmdComAddr.Text='' then
  Edit_CmdComAddr.Text:='FF';
  fComAdr := StrToInt('$' + Edit_CmdComAddr.Text); // $FF;
  try
      if ComboBox_COM.ItemIndex = 0 then //Auto
      begin
        fbaud:=ComboBox_baud2.ItemIndex;
        if fbaud>2 then fbaud:=fbaud+2;
        openresult := AutoOpenComPort(port,fComAdr,fBaud,frmcomportindex);
        fOpenComIndex := frmcomportindex;
        if openresult = 0 then
        begin
          if(fBaud>3)then
            ComboBox_baud.ItemIndex:=fBaud-2
          else
            ComboBox_baud.ItemIndex:=fBaud;
          Action_GetReaderInformationExecute(Sender); //自动执行读取写卡器信息
          if (fCmdRet=$35) or (fCmdRet=$30)then
          begin
           Application.MessageBox('Serial Communication Error or Occupied', 'Information', MB_ICONINFORMATION);
           CloseSpecComPort(frmcomportindex) ;
           exit;
          end;
        end;
      end
      else
      begin
        port := strtoint(copy(ComboBox_COM.items[ComboBox_COM.itemindex],5,3));
        for i:=6 downto 0 do
        begin     //
          fBaud:=i;
          if(fBaud=3) or (fBaud=4)then
          Continue;
          openresult := opencomport(port,fComAdr,fBaud,frmcomportindex);
          fOpenComIndex := frmcomportindex;
          if openresult= $35 then
          begin
            Application.MessageBox('COM Opened', 'Information',MB_ICONINFORMATION);
            Exit;
          end;
          if openresult = 0 then
          begin
            if(fBaud>3)then
              ComboBox_baud.ItemIndex:=fBaud-2
            else
              ComboBox_baud.ItemIndex:=fBaud;
            Action_GetReaderInformationExecute(Sender); //自动执行读取写卡器信息
            if (fCmdRet=$35) or (fCmdRet=$30)then
            begin
             Application.MessageBox('Serial Communication Error or Occupied', 'Information', MB_ICONINFORMATION);
             CloseSpecComPort(frmcomportindex) ;
            end;
            Break;
          end;
        end;
      end;
  finally
    Screen.Cursor := crDefault;
  end;

  if (fOpenComIndex <> -1) and
     (openresult <> $35)  and
     (openresult <> $30)  then
  begin
    ComboBox_AlreadyOpenCOM.Items.Add('COM'+inttostr(fOpenComIndex)) ;
    ComboBox_AlreadyOpenCOM.ItemIndex := ComboBox_AlreadyOpenCOM.ItemIndex + 1;
    // Button19.Enabled:=True;
    ComIsOpen:=True;
  end;
  if (fOpenComIndex = -1) and
     (openresult = $30)  then
  begin
     Application.MessageBox('Serial Communication Error', 'Information', MB_ICONINFORMATION);
  end;

  if (ComboBox_AlreadyOpenCOM.Items.Count <> 0) then
  begin
    if(Edit_ComAdr.Text<>'')then
    fComAdr := StrToInt('$' +Edit_ComAdr.Text);
    frmcomportindex := strtoint(copy(ComboBox_AlreadyOpenCOM.items[ComboBox_AlreadyOpenCOM.itemindex],4,3));
  end;
  RefreshStatus;
end;

procedure TfrmRRU9816main.Button4Click(Sender: TObject);
var
port:byte;
SelectCom :string;
begin
ClearLastInfo;
  try
    if ComboBox_AlreadyOpenCOM.itemindex < 0 then
      begin
        Application.MessageBox('Please Choose COM Port to close', 'Information', MB_ICONINFORMATION);
        exit;
      end
    else
    begin
      SelectCom := copy(ComboBox_AlreadyOpenCOM.Items[ComboBox_AlreadyOpenCOM.ItemIndex],4,2);
      port := strtoint(SelectCom);
      fComAdr := CloseSpecComPort(port) ;
      if fComAdr  = 0 then
      begin
        ComIsOpen:=False;
        ComboBox_AlreadyOpenCOM.DeleteSelected;
        if ComboBox_AlreadyOpenCOM.items.Count <> 0 then
          begin
            ComIsOpen:=True;
            port := strtoint(copy(ComboBox_AlreadyOpenCOM.items[0],4,2));
            CloseSpecComPort(port);
            fComAdr := $FF;
            opencomport(port,fComAdr,fBaud,frmcomportindex);
            fOpenComIndex := frmcomportindex;
            RefreshStatus;
            Action_GetReaderInformationExecute(Sender); //自动执行读取写卡器信息
          end;
      end
      else
      begin
        Application.MessageBox('Serial Communication Error', 'Information', MB_ICONINFORMATION);
        exit;
      end;
    end;
  finally

  end;

  if ComboBox_AlreadyOpenCOM.items.Count <> 0 then
    ComboBox_AlreadyOpenCOM.ItemIndex := 0
  else
  begin
    fOpenComIndex := -1;
    ComboBox_AlreadyOpenCOM.clear;
    ComboBox_AlreadyOpenCOM.Repaint;
    RefreshStatus;
  end;
end;
procedure TfrmRRU9816main.AddCmdLog(cmd, cmdName: string; cmdRet: Byte; errorCode: LongInt = -1); //操作状态成功或错误提示函数
var
  s: string;
begin
  if cmdRet <> 0 then
  begin
    s := ' “' + cmdName + '” Command Response=0x' + IntToHex(cmdRet, 2) + '(' + RRU9816_GetReturnCodeDesc(cmdRet) + ')';
    if ErrorCode <> -1 then
    begin
        s := s + #13#10 + 'ErrorCode=0x' + IntToHex(ErrorCode, 2) + '(' + RRU9816_GetErrorCodeDesc(ErrorCode) + ')';
      Application.MessageBox(pchar(s), 'Error Information', MB_ICONINFORMATION);
    end;
  end;
  ferrorcode:=-1;
  if cmdRet = 0 then
    StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) + ' “' + cmdName + '” : successfully'
  else
    StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) + '' + s;
end;

procedure TfrmRRU9816main.AddCmdLog2(cmd, cmdName: string; cmdRet: Byte; CMDReturn:string;errorCode: LongInt = -1); //操作状态成功或错误提示函数
var
  s: string;
begin
  if cmdRet <> 0 then
  begin
    s := ' “' + cmdName + '” Command Response=0x' + IntToHex(cmdRet, 2) + '(' + CMDReturn + ')';
    if ErrorCode <> -1 then
    begin
        s := s + #13#10 + 'ErrorCode=0x' + IntToHex(ErrorCode, 2) + '(' + RRU9816_GetErrorCodeDesc(ErrorCode) + ')';
      Application.MessageBox(pchar(s), 'Error Information', MB_ICONINFORMATION);
    end;
  end;
  ferrorcode:=-1;
  if cmdRet = 0 then
    StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) + ' “' + cmdName + '” : successfully'
  else
    StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) + '' + s;
end;
procedure TfrmRRU9816main.ClearLastInfo;
begin
  ComboBox_AlreadyOpenCOM.Repaint;
  RefreshStatus;
  Edit_Type.Text := '';
  Edit_Version.Text := '';
  ISO180006B.Checked:=False;
  EPCC1G2.Checked:=False;
  Edit_ComAdr.Text := '';
  Edit_power.Text := '';
  Edit_scantime.Text := '';
  Edit_dminfre.Text := '';
  Edit_dmaxfre.Text := '';
  PageControl1.TabIndex := 0;
end;
procedure TfrmRRU9816main.Action_GetReaderInformationExecute(
  Sender: TObject);
function getNoStr(no: Integer; noLen: Integer): string;
begin
  result := intToStr(no);
  while Length(result) < noLen do
    result := '0' + result;
end;
var
  VersionInfo: array[0..2] of Char;
  ScanTime,dmaxfre,dminfre,powerdBm,FreBand,TrType,Ant,BeepEn,OutputRep,CheckAnt: Byte;
  i:Integer;
begin
  Edit_Version.Text := '';
  Edit_ComAdr.Text := '';
  Edit_ScanTime.Text := '';
  Edit_Type.text := '';
  ISO180006B.Checked:=False;
  EPCC1G2.Checked:=False;
  Edit_Power.text := '';
  Edit_dminfre.text := '';
  Edit_dmaxfre.text := '';
  fCmdRet:=GetReaderInformation(fComAdr,@VersionInfo,ReaderType,TrType, dmaxfre ,dminfre,powerdBm,
                                 ScanTime,Ant,BeepEn,OutputRep,CheckAnt,frmComPortindex);
 if(fCmdRet=0)then
 begin
  Edit_Version.Text := getnostr(Ord(versioninfo[0]),2)+'.'+getnostr(Ord(versioninfo[1]),2);
  Edit_ComAdr.Text := IntToHex(fComAdr,2);
  Edit_NewComAdr.Text := IntToHex(fComAdr,2);
  Edit_ScanTime.Text := inttostr(ScanTime)+'*100ms';
  ComboBox_scantime.ItemIndex:= scantime-3;

 FreBand:= ((dmaxfre and $c0)shr 4)or(dminfre shr 6) ;
 case FreBand of
 $01:begin
         RadioButton_band2.Checked:=True;
         fdminfre := 920.125+(dminfre and $3F)*0.25;
         fdmaxfre := 920.125+(dmaxfre and $3F)*0.25;
     end;
 $02:begin
         RadioButton_band3.Checked:=True;
         fdminfre := 902.75+(dminfre and $3F)*0.5;
         fdmaxfre := 902.75+(dmaxfre and $3F)*0.5;
     end;
 $03:begin
         RadioButton_band4.Checked:=True;
         fdminfre := 917.1+(dminfre and $3F)*0.2;
         fdmaxfre := 917.1+(dmaxfre and $3F)*0.2;
     end;
  $04:begin
         RadioButton_band5.Checked:=True;
         fdminfre := 865.1+(dminfre and $3F)*0.2;
         fdmaxfre := 865.1+(dmaxfre and $3F)*0.2;
     end;
 end;
  Edit_dminfre.Text := FloatToStr(fdminfre)+'MHz';
  Edit_dmaxfre.Text := FloatToStr(fdmaxfre)+'MHz';
  if fdmaxfre<>fdminfre then
  CheckBox_SameFre.Checked:=False
  else
  CheckBox_SameFre.Checked:=True;
  ComboBox_dminfre.ItemIndex:=dminfre and $3F;
  ComboBox_dmaxfre.ItemIndex:=dmaxfre and $3F;
  case ReaderType of
    $0F: begin
          Edit_Type.text := 'RRU9816';
           Edit_power.Text   :=IntToStr(powerdBm);
         end;
    $10: begin
          Edit_Type.text := 'RRU9816';
           Edit_power.Text   :=IntToStr(powerdBm);
         end;
  end;
  ComboBox_PowerDbm.ItemIndex:=powerDbm;
  if (ord(TrType) and $02) = $02 then 
  begin
  ISO180006B.Checked:=True;
  EPCC1G2.Checked:=True;
  end
  else
  begin
  ISO180006B.Checked:=False;
  EPCC1G2.Checked:=False;
  end;
  case BeepEn of
  1: Radio_beepEn.Checked:=True;
  0: Radio_beepDis.Checked:=True;
  end;

 end;
 AddCmdLog('GetReaderInformation','GetReaderInformation', fCmdRet);
end;

procedure TfrmRRU9816main.ComboBox_AlreadyOpenCOMCloseUp(Sender: TObject);
var
  SelectCom:string;
  port :byte;
begin
  if ComboBox_AlreadyOpenCOM.items.count <>0 then
    begin
      SelectCom := copy(ComboBox_AlreadyOpenCOM.Items[ComboBox_AlreadyOpenCOM.ItemIndex],4,3);
      port := strtoint(SelectCom);
      CloseSpecComPort(port);
      fComAdr := $FF;
      if opencomport(port,fComAdr,fBaud,frmcomportindex) <> 0 then
          begin
            Application.MessageBox('Serial Communication Error', 'Information', MB_ICONINFORMATION);
            exit;
          end;
      fOpenComIndex := frmcomportindex;
      ClearLastInfo;
      RefreshStatus;
      Action_GetReaderInformationExecute(Action_GetReaderInformation); //自动执行读取写卡器信息
    end;
end;

procedure TfrmRRU9816main.Action_SetReaderInformationExecute(
  Sender: TObject);
var
  aNewComAdr,powerDbm,dminfre, dmaxfre ,scantime,band: Byte;
  returninfo:string;
  returninfoDlg:string;
  setinfo:string;
begin
  frmprogress.Show;
  frmRRU9816main.Enabled:=False;
  if(RadioButton_band2.Checked)then
  band:=1;
  if(RadioButton_band3.Checked)then
  band:=2;
  if(RadioButton_band4.Checked)then
  band:=3;
  if(RadioButton_band5.Checked)then
  band:=4;
  frmprogress.ProgressBar1.Position:=0;
  if Sender = Action_SetReaderInformation then
  begin
    dminfre := ((band and 3)shl 6)or (ComboBox_dminfre.ItemIndex and $3F) ;
    dmaxfre := ((band and $c)shl 4)or (ComboBox_dmaxfre.ItemIndex and $3F) ;
    aNewComAdr := StrToInt('$' + Edit_NewComAdr.Text);
    powerDbm:=ComboBox_PowerDbm.ItemIndex;
    fbaud:=ComboBox_baud.ItemIndex;
    if fbaud>2 then fbaud:=fbaud+2;
    scantime:= ComboBox_scantime.ItemIndex+3;
    setinfo:=' Write';
  end
  else
  begin
    dminfre := 64;
    dmaxfre := 19;
    aNewComAdr :=$00;
    powerDbm:=26;
    fbaud:=5;
    scantime:=10;
    setinfo:=' Restore';
    ComboBox_baud.itemindex:=3;
    RadioButton_band2.Checked:=True;
  end;
  frmprogress.ProgressBar1.StepBy(25);
  fCmdRet := SetAddress(fComAdr, aNewComAdr,frmcomportindex);
  if fCmdRet=ParameterSaveFailCanUseBeforeNoPower then
  fComAdr := aNewComAdr;
  if fCmdRet = 0 then
  begin
    fComAdr := aNewComAdr;
    returninfo:=returninfo+setinfo+'Address Successfully';
  //  Action_GetReaderInformationExecute(Sender);
  end
  else if fCmdRet=RecmdErr then
  returninfo:=returninfo+setinfo+'Address Response Command Error'
  else
  begin
  returninfo:=returninfo+setinfo+'Address Fail';
  returninfoDlg:=returninfoDlg+setinfo+'Address Fail Command Response=0x'
       +inttostr(fCmdRet)+'('+RRU9816_GetReturnCodeDesc(fCmdRet)+')';
  end;
  frmprogress.ProgressBar1.StepBy(25);
  fCmdRet := SetRfPower(fComAdr,powerDbm,frmcomportindex);
  if fCmdRet = 0 then
   returninfo:=returninfo+setinfo+'Power Success'
  else if fCmdRet=RecmdErr then
  returninfo:=returninfo+setinfo+'Power Response Command Error'
  else
  begin
  returninfo:=returninfo+setinfo+'Power Fail';
  returninfoDlg:=returninfoDlg+#13#10+setinfo+'Power Fail Command Response 0x='
       +inttostr(fCmdRet)+'('+RRU9816_GetReturnCodeDesc(fCmdRet)+')';
  end;

  frmprogress.ProgressBar1.StepBy(25);
  fCmdRet := SetRegion(fComAdr,dmaxfre,dminfre,frmcomportindex);
  if fCmdRet = 0 then
   returninfo:=returninfo+setinfo+'Region Success'
  else if fCmdRet=RecmdErr then
  returninfo:=returninfo+setinfo+'Region Response Command Error'
  else
  begin
  returninfo:=returninfo+setinfo+'Region Fail';
  returninfoDlg:=returninfoDlg+#13#10+setinfo+'Region Fail Command Response0x='
       +inttostr(fCmdRet)+'('+RRU9816_GetReturnCodeDesc(fCmdRet)+')';
  end;

  frmprogress.ProgressBar1.StepBy(25);
  fCmdRet := SetBaudRate(fComAdr, fBaud,frmcomportindex);
  if fCmdRet = 0 then
   returninfo:=returninfo+setinfo+'BaudRate Success'
  else if fCmdRet=RecmdErr then
  returninfo:=returninfo+setinfo+'BaudRate Response Command Error'
  else
  begin
  returninfo:=returninfo+setinfo+'BaudRate Fail';
  returninfoDlg:=returninfoDlg+#13#10+setinfo+'BaudRate Fail Command Response0x='
       +inttostr(fCmdRet)+'('+RRU9816_GetReturnCodeDesc(fCmdRet)+')';
  end;

  frmprogress.ProgressBar1.StepBy(25);
  fCmdRet := SetInventoryScanTime(fComAdr, scantime,frmcomportindex);
  if fCmdRet = 0 then
   returninfo:=returninfo+setinfo+'InventoryScanTime Success'
  else if fCmdRet=RecmdErr then
  returninfo:=returninfo+setinfo+'InventoryScanTime Response Command Error0x'
  else
  begin
  returninfo:=returninfo+setinfo+'InventoryScanTime Fail';
  returninfoDlg:=returninfoDlg+#13#10+setinfo+'InventoryScanTime Fail Command Response='
       +inttostr(fCmdRet)+'('+RRU9816_GetReturnCodeDesc(fCmdRet)+')';
  end;

  Action_GetReaderInformationExecute(Sender);
  frmprogress.Close;
  frmRRU9816main.Enabled:=True;
  StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  returninfo;
  if  returninfoDlg<>'' then
  MessageDlg(returninfoDlg, mtInformation, [mbOK], 0);
end;

procedure TfrmRRU9816main.RadioButton_band2Click(Sender: TObject);
var
  i:Integer;
begin
  CheckBox_SameFre.Checked:=False;
  ComboBox_dminfre.Items.Clear;
  ComboBox_dmaxfre.Items.Clear;
 for i:=0 to 19 do
  begin
    ComboBox_dminfre.Items.Add(floattostr(920.125+i*0.25)+' MHz');
    ComboBox_dmaxfre.Items.Add( floattostr(920.125+i*0.25)+' MHz');
  end;
  ComboBox_dminfre.ItemIndex := 0;
  ComboBox_dmaxfre.ItemIndex := 19;
end;

procedure TfrmRRU9816main.RadioButton_band3Click(Sender: TObject);
var
  i:Integer;
begin
  CheckBox_SameFre.Checked:=False;
  ComboBox_dminfre.Items.Clear;
  ComboBox_dmaxfre.Items.Clear;
 for i:=0 to 49 do
  begin
    ComboBox_dminfre.Items.Add(floattostr(902.75+i*0.5)+' MHz');
    ComboBox_dmaxfre.Items.Add( floattostr(902.75+i*0.5)+' MHz');
  end;
  ComboBox_dminfre.ItemIndex := 0;
  ComboBox_dmaxfre.ItemIndex := 49;
end;

procedure TfrmRRU9816main.RadioButton_band4Click(Sender: TObject);
var
  i:Integer;
begin
  CheckBox_SameFre.Checked:=False;
  ComboBox_dminfre.Items.Clear;
  ComboBox_dmaxfre.Items.Clear;
  for i:=0 to 31 do
  begin
    ComboBox_dminfre.Items.Add(floattostr(917.1+i*0.2)+' MHz');
    ComboBox_dmaxfre.Items.Add( floattostr(917.1+i*0.2)+' MHz');
  end;
  ComboBox_dminfre.ItemIndex:=0;
  ComboBox_dmaxfre.ItemIndex:=31;
end;

procedure TfrmRRU9816main.RadioButton_band5Click(Sender: TObject);
var
  i:Integer;
begin
  CheckBox_SameFre.Checked:=False;
  ComboBox_dminfre.Items.Clear;
  ComboBox_dmaxfre.Items.Clear;
 for i:=0 to 14 do
  begin
    ComboBox_dminfre.Items.Add(floattostr(865.1+i*0.2)+' MHz');
    ComboBox_dmaxfre.Items.Add( floattostr(865.1+i*0.2)+' MHz');
  end;
  ComboBox_dminfre.ItemIndex:=0;
  ComboBox_dmaxfre.ItemIndex:=14;
end;

procedure TfrmRRU9816main.Action_GetReaderInformationUpdate(
  Sender: TObject);
begin
  Button3.Enabled:=ComIsOpen;
  Button5.Enabled:=ComIsOpen;
  Button1.Enabled:=ComIsOpen;
  Button_Beep.Enabled:=ComIsOpen;
  Button_SetGPIO.Enabled:=ComIsOpen;
  Button_GetGPIO.Enabled:=ComIsOpen;
  Button21.Enabled:=ComIsOpen ;
  Button8.Enabled:=ComIsOpen ;
  bt_getlen.Enabled:=ComIsOpen;
  bt_setlen.Enabled:=ComIsOpen;
end;

function TfrmRRU9816main.RoundClassic(R: Real): Int64;
begin
Result:= Trunc(R);
if Frac(R) >= 0.5 then
    Result:= Result + 1;
end;
procedure TfrmRRU9816main.CheckBox_SameFreClick(Sender: TObject);
begin
    if CheckBox_SameFre.Checked then
    ComboBox_dmaxfre.ItemIndex:=ComboBox_dminfre.ItemIndex;
end;

procedure TfrmRRU9816main.Edit2KeyPress(Sender: TObject; var Key: Char);
  var L:Boolean;
begin
    L:=(key<#8)or(key>#8)and(key<#48)or(key>#57)and (key<#65)or(key>#70)and (key<#97)or(key>#102);
    if l then key:=#0;
    if ( (key>#96)and(key<#103))   then  key:=  char(Ord(key)-32) ;
end;

procedure TfrmRRU9816main.SpeedButton_QueryClick(Sender: TObject);
var
   i:   Integer;
begin
  Target:=0;
  if(CheckBox_TID.Checked)then
  begin
    if(Length(Edit13.Text)<>2)or(Length(Edit14.Text)<>2)then
    begin
     StatusBar1.Panels[0].Text:='TID Parameter Error';
     SpeedButton_Query.down:=False;
     Exit;
    end;
  end;
  if((Edit2.Text='')or(Edit3.Text=''))then
  begin
    StatusBar1.Panels[0].Text:='Mask adress or Length is Null';
    SpeedButton_Query.down:=False;
    Exit;
  end;
  if(CheckBox1.Checked)then
  begin
    if(Length(Edit1.Text)mod 2<>0)then
    begin
      StatusBar1.Panels[0].Text:='Mask Data error';
      SpeedButton_Query.down:=False;
      Exit;
    end;
  end;
  if not (SpeedButton_Query.down) then
  begin
    AddCmdLog('Inventory', 'Exit Query', 0);
    Timer_Test_.Enabled:=False;
    Edit13.Enabled:=true;
    Edit14.Enabled:=true;
    CheckBox_TID.Enabled:=true;
  end
  else
  begin
    fInventory_EPC_List := ''; //先清除原来的缓冲
    ListView_EPC.Items.Clear;
    Suc_count:=0;
    Query_count:=0;
    card_Count:=0;
    Timer_Test_.Enabled:=True;
    ListView_EPC.Clear;
    ComboBox_EPC1.Clear;
    ComboBox_EPC2.Clear;
    ComboBox_EPC3.Clear;
    ComboBox_EPC4.Clear;
    ComboBox_EPC5.Clear;
    ComboBox_EPC6.Clear;
    Edit13.Enabled:=false;
    Edit14.Enabled:=false;
    CheckBox_TID.Enabled:=false;
    Edit18.Text:='';
    Edit17.Text:='';
  end;
end;

procedure TfrmRRU9816main.Action_InventoryExecute(Sender: TObject);
 procedure ChangeSubItem1(aListItem: TListItem; subItemIndex: Integer; ItemText: string;ant1,RSSI:string);
  begin
    //if aListItem.SubItems[subItemIndex] = ItemText then
    begin
      if(aListItem.SubItems[2]='')then
      begin
         aListItem.SubItems[2]:=ant1;
      end
      else
      begin
         aListItem.SubItems[2]:=Str_IntToBin(StrToInt('$'+BitStrToHextStr(aListItem.SubItems[2]))or StrToInt('$'+BitStrToHextStr(ant1)),4) ;
      end;
      if (aListItem.SubItems[3]='99999') or (aListItem.SubItems[3]='')then              //aListItem.SubItems[2]为次数
       aListItem.SubItems[3]:='0'                        //aListItem.SubItems[0]为 EPC号
      else
      begin
       aListItem.SubItems[3]:= IntToStr(StrToInt(aListItem.SubItems[3])+1);
       aListItem.SubItems[4]:=RSSI;
       exit; //内容相同则不需要修改，可以不闪烁
      end;
    end;

  end;
  procedure ChangeSubItem2(aListItem: TListItem; subItemIndex: Integer; ItemText: string;ant1,RSSI:string);
  begin
   { if aListItem.SubItems[subItemIndex] = ItemText then         //aListItem.SubItems[1]为 EPC长度
    exit; //内容相同则不需要修改，可以不闪烁
    aListItem.SubItems[subItemIndex] := ItemText;  }
    aListItem.SubItems[1]:= IntToStr(Length(ItemText)div 2) ;
    aListItem.SubItems[2]:=ant1;
    aListItem.SubItems[3]:='1';
    aListItem.SubItems[4]:=RSSI;
    aListItem.SubItems[subItemIndex] := ItemText;
  end;
var
  CardNum:Integer;
  EPClen,m,Totallen:Integer;
  EPC: array[0..5000] of Char;
  isonstring:Boolean;
  isonlistview:Boolean;
  CardIndex: Integer;
  temps: string;
  s,ss, s2,sEPC: string;
  aListItem: TListItem;
  temp1,temp2,temps2, temps3: string;
  i, j,n_index: integer;
  baifenbi:Real;
  MaskMem:Byte;
  MaskAdr:array[0..2]of Char;
  MaskLen:Byte;
  MaskData:array[0..80]of Char;
  MaskFlag:Byte;
  Ant:Byte;
  antstr,lastepc:string;
  Qvalue,Session:Byte;
  AdrTID,LenTID,TIDFlag:Byte;
  RSSI:string;
  m_ant:LongInt;
  queryFlag:Boolean;
begin
  Inant := $80;
  ScanTime:=ComboBox1.ItemIndex+3;
  FastFlag:=0;
  FillChar( MaskData,80,0);
  if(R_EPC.Checked)then MaskMem:=1;
  if(R_TID.Checked)then MaskMem:=2;
  if(R_User.Checked)then MaskMem:=3;
  getCharStr(Edit2.Text,MaskAdr);
  if(CheckBox1.Checked)then
  MaskFlag:=1
  else
  MaskFlag:=0;
  QValue:=Com_Q.ItemIndex;
  Session:=Com_S.ItemIndex;
  MaskLen:=StrToInt('$'+trim(edit3.Text));
  getCharStr(Edit1.Text,MaskData);
  if(CheckBox_TID.Checked)then
  begin
    AdrTID:=StrToInt('$'+Trim(Edit13.Text));
    LenTID:=StrToInt('$'+Trim(Edit14.Text));
    TIDFlag:=1;
  end
  else
  begin
    AdrTID:=0;
    LenTID:=0;
    TIDFlag:=0;
  end;
  try
     CardNum:=0;
     FastFlag:=1;
     if (Session = 0) or (Session=1) then
     begin
       Target:=0;
     end
     else
     begin
       if(AA_times > 1)then
       begin
         Target:=1- Target;
       end;
     end;
     fCmdRet :=Inventory_G2(fComAdr,QValue,Session,MaskMem,@MaskAdr,MaskLen,@MaskData,MaskFlag,AdrTID,LenTID,TIDFlag,Target,InAnt,Scantime,FastFlag,@EPC,Ant,Totallen,CardNum,frmcomportindex);
     AddCmdLog('Inventory', 'Inventory', fCmdRet);
     Query_count:=Query_count+1;
     if(fCmdRet = $01)or (fCmdRet = $02)or (fCmdRet = $03)or (fCmdRet = $04)or(fCmdRet = $FB)  then //代表已查找结束，并且内容有发生变化
    begin
      if(CardNum=0)then
      begin
        AA_times:=AA_times+1;
      end
      else
      begin
        AA_times:=0;
      end;
      temps :=getStr(EPC,Totallen);
      m:=1;
      for CardIndex := 1 to CardNum do
      begin
        EPClen:=ord(tempS[m])+2;
        sEPC := copy(tempS,m,EPClen) ;
        m:=m+EPClen;
        if Length(sEPC) <> EPClen then Exit;
        s := getHexStr(sEPC);
        RSSI:= IntToStr(StrToInt('$'+copy(s,Length(s)-1,2)));
        isonlistview:=False;
        s2:= copy(s, 3, Length(s)-4);
        for i:=1 to ListView_EPC.Items.Count do      //判断是否在Listview列表内
        begin
          if s2=(ListView_EPC.Items[i - 1]).SubItems[0] then
          begin
           aListItem := ListView_EPC.Items[i - 1];
           ChangeSubItem1(aListItem, 0, S2, Str_IntToBin(Ant,4),RSSI);
           isonlistview:=True;
           Break;
          end;
        end;
        if (not isonlistview) then
        begin
          aListItem := ListView_EPC.Items.Add;
          aListItem.Caption := IntToStr(aListItem.Index + 1);
          aListItem.SubItems.Add('');
          aListItem.SubItems.Add('');
          aListItem.SubItems.Add('');
          aListItem.SubItems.Add('');
          aListItem.SubItems.Add('');
          aListItem := ListView_EPC.Items[ListView_EPC.Items.Count - 1];
          ChangeSubItem2(aListItem, 0, S2, Str_IntToBin(Ant,4),RSSI);
          if(not CheckBox_TID.Checked)then
          begin
          ComboBox_EPC1.Items.Add(S2);
          ComboBox_EPC2.Items.Add(S2);
          ComboBox_EPC3.Items.Add(S2);
          ComboBox_EPC4.Items.Add(S2);
          ComboBox_EPC5.Items.Add(S2);
          ComboBox_EPC6.Items.Add(S2);
          end;
          Application.ProcessMessages;
        end;
        if(s<>'')then lastepc:=S2;
      end;
      if(ListView_EPC.Items.Count>0)then
      begin
        if ((Query_count > 1) or (Session = 0))then
        Edit18.Text:=IntToStr(ListView_EPC.Items.Count);
        Edit17.Text:= lastepc;
        ListView_EPC.ItemIndex := ListView_EPC.Items.Count -1;
        ListView_EPC.Selected.MakeVisible(False);
        if(not CheckBox_TID.Checked)then
        begin
        ComboBox_EPC1.Itemindex:=0;
        ComboBox_EPC2.Itemindex:=0;
        ComboBox_EPC3.Itemindex:=0;
        ComboBox_EPC4.Itemindex:=0;
        ComboBox_EPC5.Itemindex:=0;
        ComboBox_EPC6.Itemindex:=0;
        end;
      end;
    end;
  finally

  end;
end;

procedure TfrmRRU9816main.Timer_Test_Timer(Sender: TObject);
begin
 if fisinventoryscan then    Exit;
    fIsInventoryScan := true;
    Action_InventoryExecute(sender);
    fIsInventoryScan := False;
end;

procedure TfrmRRU9816main.ComboBox_IntervalTimeChange(Sender: TObject);
begin
Timer_Test_.Interval :=(ComboBox_IntervalTime.ItemIndex+1)*10;
end;

procedure TfrmRRU9816main.SpeedButton_Read_G2Click(Sender: TObject);
begin
    if SpeedButton_Read_G2.Down  then
    begin
      if Length(Edit_AccessCode2.Text)<8 then
      begin
        SpeedButton_Read_G2.Down:=False;
         MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
        Exit;
      end;
      if (Edit_WordPtr.Text='')or (Edit_Len.Text='')then
      begin
        SpeedButton_Read_G2.Down:=False;
        MessageDlg('Start address or length is empty!Please input!', mtInformation, [mbOK], 0);
        Exit;
      end;
    Timer_G2_Read.Enabled:=True;
    end
    else
    begin
    Timer_G2_Read.Enabled:=False;
    StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Read" over' ;
    end;
end;

procedure TfrmRRU9816main.Timer_G2_ReadTimer(Sender: TObject);
var
    Mem,Num,WordPtr:Byte;
    ENum:byte;
    i: Integer;
    s2: string;
    CardData: array[0..320] of Char;
    MaskMem:Byte;
    MaskAdr:array[0..2]of Char;
    MaskLen:Byte;
    MaskData:array[0..80]of Char;
begin
  FillChar( MaskData,80,0);
  if  fTimer_G2_Read then    exit;
  fTimer_G2_Read:=true;
  try
    if SpeedButton_Read_G2.Down  then
    begin
      if(R_EPC.Checked)then MaskMem:=1;
      if(R_TID.Checked)then MaskMem:=2;
      if(R_User.Checked)then MaskMem:=3;

      if(CheckBox1.Checked)then
      begin
      ENum:=255;
      if(Edit2.Text='')then Exit;
      if(Edit3.Text='')then Exit;
      if(Edit1.Text='')or(Length(Edit1.Text)mod 2<>0)then Exit;
      getCharStr(Edit2.Text,MaskAdr);
      MaskLen:=StrToInt('$'+trim(edit3.Text));
      getCharStr(Edit1.Text,MaskData);
      END
      else
       ENum:=Length(ComboBox_EPC2.text) div 4;

      getCharStr(ComboBox_EPC2.text,fOperEPC);
      getCharStr(Edit_AccessCode2.text,fPassword);
      WordPtr:=StrToInt('$'+Edit_WordPtr.Text);
      Num:=StrToInt(Edit_Len.Text);
      if  C_Reserve.Checked then
        Mem:=0
      else if  C_EPC.Checked then
        Mem:=1
      else if  C_TID.Checked then
        Mem:=2
      else if  C_User.Checked then
        Mem:=3;
      fCmdRet:=ReadData_G2(fComAdr,@fOperEPC,ENum,Mem,WordPtr,Num,@fPassword,MaskMem,@MaskAdr,MaskLen,MaskData,@CardData,ferrorcode,frmComPortindex);
      if fCmdRet=0 then
      begin
        for i := 0 to Num*2 - 1 do
        s2 := s2 + IntToHex(ord(CardData[i]), 2);
        Memo_DataShow.Lines.Add(s2);
      end;
      if  fErrorCode<>-1 then
      begin
      StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +
       ' "Read" Response ErrorCode=0x'+ IntToHex(fErrorCode, 2) +
       '(' + RRU9816_GetErrorCodeDesc(fErrorCode) + ')';
        ferrorcode:=-1;
      end
      else
      AddCmdLog('ReadData','Read', fCmdRet);
      if not (SpeedButton_Read_G2.Down)  then
      StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  '"Read" over' ;
    end;
  finally
  fTimer_G2_Read:=false;
  end;
  if fAppClosed then Close;
end;

procedure TfrmRRU9816main.Action_ShowOrChangeDataExecuteExecute(
  Sender: TObject);
var
    Mem,Num,WordPtr:Byte;
    Writedata:array[0..320] of Char;
    WNum:Byte;
    ENum:Byte;
    EPClength:byte;
    i: Integer;
    s,s2: string;
    CardData: array[0..320] of Char;
    WrittenDataNum:LongInt;
    MaskMem:Byte;
    MaskAdr:array[0..2]of Char;
    MaskLen:Byte;
    MaskData:array[0..80]of Char;
begin
      FillChar( MaskData,80,0);
      if(R_EPC.Checked)then MaskMem:=1;
      if(R_TID.Checked)then MaskMem:=2;
      if(R_User.Checked)then MaskMem:=3 ;
      if(CheckBox1.Checked)then
      begin
       ENum:=255;
        if(Edit2.Text='')then Exit;
        if(Edit3.Text='')then Exit;
        if(Edit1.Text='')or(Length(Edit1.Text)mod 2<>0)then Exit;
        getCharStr(Edit2.Text,MaskAdr);
        MaskLen:=StrToInt('$'+trim(edit3.Text));
        getCharStr(Edit1.Text,MaskData);
      end
      else
       ENum:=Length(ComboBox_EPC2.text) div 4;
      if Length(Edit_AccessCode2.Text)<8 then
      begin
       MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
        Exit;
      end;
      if (Edit_WordPtr.Text='')or(Edit_Len.Text='')then
      begin
       MessageDlg('Start address or length is empty!Please input!', mtInformation, [mbOK], 0);
        Exit;
      end;
    getCharStr(ComboBox_EPC2.text,fOperEPC);
    getCharStr(Edit_AccessCode2.text,fPassword);
    WordPtr:=StrToInt('$'+Edit_WordPtr.Text);
    Num:=StrToInt(Edit_Len.Text);
    if  C_Reserve.Checked then
      Mem:=0
    else if  C_EPC.Checked then
      Mem:=1
    else if  C_TID.Checked then
      Mem:=2
    else if  C_User.Checked then
      Mem:=3;
    if Sender=Action_ShowOrChangeData_write then
    begin
      if ( Edit_WriteData.Text='' )or (Length(Edit_WriteData.Text)mod 4<>0) then
      begin
      MessageDlg('Please input Data in words in hexadecimal form!'+#13+#10+'For example: 1234、12345678', mtInformation, [mbOK], 0);
      Exit;
      end;
      WNum:= Length(Edit_WriteData.text)div 4 ;
      getCharStr(Edit_WriteData.text,Writedata);
     if(CheckBox18.Checked)and(C_EPC.Checked)then
      begin
        WordPtr:=1;
       WNum:= Length(Edit_WriteData.text)div 4 +1;
       getCharStr(edit_pc.Text+Edit_WriteData.text,Writedata);
      end;
      fCmdRet:=WriteData_G2(fComAdr,@fOperEPC,WNum,ENum,Mem,WordPtr,@Writedata,@fPassword,MaskMem,@MaskAdr,MaskLen,@MaskData,ferrorcode,frmComPortindex);
      AddCmdLog('WriteData','Write', fCmdRet,ferrorcode);
      if fCmdRet=0 then
      begin
      StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Write"Command Response=0x00' +
                  '(completely write Data successfully)';
      end;
    end;
    if Sender=Action_ShowOrChangeData_BlockWrite then
    begin
      if ( Edit_WriteData.Text='' )or (Length(Edit_WriteData.Text)mod 4<>0) then
      begin
      MessageDlg('Please input Data in words in hexadecimal form!'+#13+#10+'For example: 1234、12345678', mtInformation, [mbOK], 0);
      Exit;
      end;
      WNum:= Length(Edit_WriteData.text)div 4 ;
      getCharStr(Edit_WriteData.text,Writedata);
      if(CheckBox18.Checked)and(C_EPC.Checked)then
      begin
        WordPtr:=1;
       WNum:= Length(Edit_WriteData.text)div 4 +1;
       getCharStr(edit_pc.Text+Edit_WriteData.text,Writedata);
      end;
      fCmdRet:=BlockWrite_G2(fComAdr,@fOperEPC,WNum,ENum,Mem,WordPtr,@Writedata,@fPassword,MaskMem,@MaskAdr,MaskLen,@MaskData,ferrorcode,frmComPortindex);
      AddCmdLog('BlockWrite','Block Write', fCmdRet,ferrorcode);
      if fCmdRet=0 then
      begin
      StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' “"BlockWrite"Command Response=0x00' +
                  '(completely Blockwrite Data successfully)';
      end;
    end;
    if Sender=Action_ShowOrChangeData_BlockErase then
    begin
      if Length(Edit_AccessCode2.Text)<8 then
      begin
        MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
        Exit;
      end;
      if (Edit_WordPtr.Text='')or (Edit_Len.Text='')then
      begin
        SpeedButton_Read_G2.Down:=False;
       MessageDlg('Start address or Length of Block erase is empty!Please input!', mtInformation, [mbOK], 0);
        Exit;
      end;
      if (strtoint('$'+Edit_WordPtr.Text)<1)and C_EPC.checked then
      begin
       MessageDlg('the length of start Address of erasing EPC area is equal or greater than 0x01!', mtInformation, [mbOK], 0);
        Exit;   //
      end;
      fCmdRet:=BlockErase_G2(fComAdr,@fOperEPC,ENum,Mem,WordPtr,Num,@fPassword,MaskMem,@MaskAdr,MaskLen,@MaskData,ferrorcode,frmComPortindex);
      AddCmdLog('BlockErase', 'Erase Block', fCmdRet,ferrorcode);
      if fCmdRet=0 then
      begin
      StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' “Block Erase”Command Response=0x00' +
                '(Block Erase successfully)';
      end;
    end;
end;

procedure TfrmRRU9816main.Action_SetProtectStateExecute(Sender: TObject);
var
  select:byte;
  setprotect:Byte;
  return:Integer;
  ENum:Byte;
  MaskMem:Byte;
  MaskAdr:array[0..2]of Char;
  MaskLen:Byte;
  MaskData:array[0..80]of Char;
begin
    if(R_EPC.Checked)then MaskMem:=1;
    if(R_TID.Checked)then MaskMem:=2;
    if(R_User.Checked)then MaskMem:=3;
    FillChar( MaskData,80,0);
    if(CheckBox1.Checked)then
    begin
     ENum:=255;
     if(Edit2.Text='')then Exit;
     if(Edit3.Text='')then Exit;
     if(Edit1.Text='')or(Length(Edit1.Text)mod 2<>0)then Exit;
        MaskLen:=StrToInt('$'+trim(edit3.Text));
     getCharStr(Edit1.Text,MaskData);
     getCharStr(Edit2.Text,MaskAdr);
    end
    else
     ENum:=Length(ComboBox_EPC1.text) div 4;

    getCharStr(ComboBox_EPC1.text,fOperEPC);
    getCharStr(Edit_AccessCode1.text,fPassword);
    if P_Reserve.Checked and DestroyCode.Checked  then
     select:=$00
    else if P_Reserve.Checked and AccessCode.Checked then
     select:=$01
    else if P_EPC.Checked then
     select:=$02
    else if P_TID.Checked then
     select:=$03
    else if P_User.Checked then
     select:=$04;
    if P_Reserve.Checked then
    begin
      if NoProect.Checked then
       setprotect:=$00
      else if Proect.Checked then
       setprotect:=$02
      else if Always.Checked then
      begin
       setprotect:=$01;
        return:=MessageDlg('Set permanently readable and writeable Confirmed?', mtInformation, [mbOK, mbCancel], 0);
       if return = IDCancel then
       Exit;
      end
      else if AlwaysNot.Checked then
      begin
       setprotect:=$03;
       return:=MessageDlg('Set never readable and writeable Confirmed?', mtInformation, [mbOK, mbCancel], 0);
       if return = IDCancel then
       Exit;
      end;
    end
    else
    begin
      if NoProect2.Checked then
       setprotect:=$00
      else if Proect2.Checked then
       setprotect:=$02
      else if Always2.Checked then
      begin
       setprotect:=$01;
       return:=MessageDlg('Set permanently writeable Confirmed?', mtInformation, [mbOK, mbCancel], 0);
       if return = IDCancel then
       Exit;
      end
      else if AlwaysNot2.Checked then
      begin
       setprotect:=$03;
       return:=MessageDlg('Set never writeable Confirmed?', mtInformation, [mbOK, mbCancel], 0);
       if return = IDCancel then
       Exit;
      end;
    end;
    if Length(Edit_AccessCode1.Text)<8 then
    begin
       MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
      Exit;
    end;
    fCmdRet:=Lock_G2(fComAdr,@fOperEPC,ENum,select,setprotect,@fPassword,MaskMem,@MaskAdr,MaskLen,@MaskData,ferrorcode,frmComPortindex);  ;
    AddCmdLog('Lock_G2', 'Lock', fCmdRet,ferrorcode);
end;

procedure TfrmRRU9816main.Action_SetProtectStateUpdate(Sender: TObject);
var
  CanEnabled:Boolean;
  CanEnabled2:Boolean;
begin
   SpeedButton_Query .Enabled:=ComIsOpen and (not (SpeedButton_CheckAlarm_G2.Down) )
                                 and (not (SpeedButton_Read_G2.Down) ) ;
//  SpeedButton_detect.Enabled:=ComIsOpen and (not (SpeedButton_CheckAlarm_G2.Down));

    CanEnabled:=not (SpeedButton_Query.down) and  ComIsOpen and (ListView_EPC.Items.Count<>0)
                and (not (SpeedButton_CheckAlarm_G2.Down))and (not (SpeedButton_Read_G2.Down) );
    CanEnabled2:=not (SpeedButton_Query.down) and  ComIsOpen
                and (not (SpeedButton_CheckAlarm_G2.Down))and (not (SpeedButton_Read_G2.Down) );
    ComboBox_IntervalTime.Enabled:= CanEnabled2;

    AccessCode.Enabled:=CanEnabled and (P_Reserve.Checked) ;
    DestroyCode.Enabled:=CanEnabled and (P_Reserve.Checked) ;
    NoProect.Enabled:=CanEnabled and (P_Reserve.Checked) ;
    Proect.Enabled:=CanEnabled and (P_Reserve.Checked) ;
    Always.Enabled:=CanEnabled and (P_Reserve.Checked) ;
    AlwaysNot.Enabled:=CanEnabled and (P_Reserve.Checked) ;

    NoProect2.Enabled:=not (P_Reserve.Checked)and CanEnabled;
    Proect2.Enabled:=not (P_Reserve.Checked)and CanEnabled;
    Always2.Enabled:=not (P_Reserve.Checked)and CanEnabled;
    AlwaysNot2.Enabled:=not (P_Reserve.Checked)and CanEnabled;

    GroupBox5.Enabled:=CanEnabled;
    Label24.Enabled:=CanEnabled;
    ComboBox_EPC1.Enabled:=CanEnabled;
    GroupBox18.Enabled:=CanEnabled;

    Edit_AccessCode1.Enabled:=CanEnabled;
    GroupBox1.Enabled:=CanEnabled;
    P_Reserve.Enabled:=CanEnabled;
    P_EPC.Enabled:=CanEnabled;
    P_TID.Enabled:=CanEnabled;
    P_User.Enabled:=CanEnabled;
    GroupBox9.Enabled:=CanEnabled;
    Label33.Enabled:=CanEnabled;
    Edit_DestroyCode.Enabled:=CanEnabled;
    ComboBox_EPC3.Enabled:=CanEnabled;

    GroupBox10.Enabled:=not (SpeedButton_Query.down) and  ComIsOpen and (ListView_EPC.Items.Count<>0)
                        and (not (SpeedButton_CheckAlarm_G2.Down));
    SpeedButton_Read_G2.Enabled:=GroupBox10.Enabled ;
    Memo_DataShow.Enabled:=GroupBox10.Enabled ;
    Button16.Enabled:=GroupBox10.Enabled ;
    
    Label9.Enabled:=CanEnabled;
    Label18.Enabled:=CanEnabled;
    Label19.Enabled:=CanEnabled;
    Label20.Enabled:=CanEnabled;
    ComboBox_EPC2.Enabled:=CanEnabled;
    Edit_AccessCode2.Enabled:=CanEnabled;
    Edit_WriteData.Enabled:=CanEnabled;
    Edit_WordPtr.Enabled:=CanEnabled;
    Edit_Len.Enabled:=CanEnabled;

    GroupBox6.Enabled:=CanEnabled;
    C_Reserve.Enabled:=CanEnabled;
    C_EPC.Enabled:=CanEnabled;
    C_TID.Enabled:=CanEnabled;
    C_User.Enabled:=CanEnabled;
    Button_SetProtectState.Enabled:=CanEnabled;
//    Button_DataRead.Enabled:=CanEnabled;

    Button_DataWrite.Enabled:=CanEnabled ;
    Button_BlockErase.Enabled:=CanEnabled;
    Button_BlockWrite.Enabled:=CanEnabled;
    Button_DestroyCard.Enabled:=CanEnabled;
   if CheckBox1.Checked and (not SpeedButton_Read_G2.Down) then
    begin
      Edit2.Enabled:=True;
      Edit3.Enabled:=True;
      Edit1.Enabled:=True;
      R_EPC.Enabled:=True;
      R_TID.Enabled:=True;
      R_User.Enabled:=True;
    end
    else
    begin
      Edit2.Enabled:=False ;
      Edit3.Enabled:=False;
      Edit1.Enabled:=False;
      R_EPC.Enabled:=False;
      R_TID.Enabled:=False;
      R_User.Enabled:=False;
    end;

    GroupBox23.Enabled:=CanEnabled2;
    Label38.Enabled:=CanEnabled2;
    Label39.Enabled:=CanEnabled2;
    Edit_AccessCode3.Enabled:=CanEnabled2;
    Button_WriteEPC_G2.Enabled:=CanEnabled2;
    Edit_WriteEPC.Enabled:=CanEnabled2;
    ExtRead.Enabled:=CanEnabled2;
    ExtWrite.Enabled:=CanEnabled2;
    ComboBox_EPC4.Enabled:=CanEnabled;
    Button_SetReadProtect_G2.Enabled:=CanEnabled;

    GroupBox20.Enabled:=CanEnabled2;
    Label32.Enabled:=CanEnabled2;
    Edit_AccessCode4.Enabled:=CanEnabled2;
    Button_SetMultiReadProtect_G2.Enabled:=CanEnabled2;
    Button_RemoveReadProtect_G2.Enabled:=CanEnabled2;
    Button_CheckReadProtected_G2.Enabled:=CanEnabled2;

    Label35 .Enabled:=CanEnabled;
    Button_SetEASAlarm_G2.Enabled:=CanEnabled;
    ComboBox_EPC5.Enabled:=CanEnabled;
    Edit_AccessCode5.Enabled:=CanEnabled;
    GroupBox24 .Enabled:=CanEnabled;
    Alarm_G2 .Enabled:=CanEnabled;
    NoAlarm_G2.Enabled:=CanEnabled;

    GroupBox21.Enabled:=not (SpeedButton_Query.down) and  ComIsOpen
                        and(not (SpeedButton_Read_G2.Down) ) ;

    SpeedButton_CheckAlarm_G2.Enabled:=GroupBox21.Enabled;

    GroupBox22.Enabled:=CanEnabled;
    Label36   .Enabled:=CanEnabled;
    Label37   .Enabled:=CanEnabled;
    Button_LockUserBlock_G2.Enabled:=CanEnabled;
    ComboBox_BlockNum.Enabled:=CanEnabled;
    ComboBox_EPC6 .Enabled:=CanEnabled;
    Edit_AccessCode6.Enabled:=CanEnabled;
end;

procedure TfrmRRU9816main.Action_DestroyCardExecute(Sender: TObject);
var
  return:Integer;
  ENum:byte;
  MaskMem:Byte;
  MaskAdr:array[0..2]of Char;
  MaskLen:Byte;
  MaskData:array[0..80]of Char;
begin
  if(Edit2.Text='')then Exit;
  if(Edit3.Text='')then Exit;
  if(Edit1.Text='')or(Length(Edit1.Text)mod 2<>0)then Exit;
  if(R_EPC.Checked)then MaskMem:=1;
  if(R_TID.Checked)then MaskMem:=2;
  if(R_User.Checked)then MaskMem:=3;
  FillChar( MaskData,80,0);
  getCharStr(Edit2.Text,MaskAdr);
  if(CheckBox1.Checked)then
  ENum:=255
  else
  ENum:=Length(ComboBox_EPC3.text) div 4;
  MaskLen:=StrToInt('$'+trim(edit3.Text));
  getCharStr(Edit1.Text,MaskData);
  return:=MessageDlg('Kill the Tag  Confirmed?', mtInformation, [mbOK, mbCancel], 0);
  if return = IDok then
  begin
    if Length(Edit_DestroyCode.Text)<8 then
    begin
      MessageDlg('Kill Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
      Exit;
    end;
    getCharStr(ComboBox_EPC3.text,fOperEPC);
    getCharStr(Edit_DestroyCode.text,fPassword);
   fCmdRet:=KillTag_G2(fComAdr,@fOperEPC,ENum,@fPassword,MaskMem,@MaskAdr,MaskLen,@MaskData,ferrorcode,frmComPortindex);
    AddCmdLog('KillTag_G2', 'Kill Tag', fCmdRet,ferrorcode);
    if fCmdRet=0 then
    begin
    StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Kill Tag"Command Response=0x00' +
              '(Kill successfully)'
    end;
  end;
end;

procedure TfrmRRU9816main.Action_WriteEPC_G2Execute(Sender: TObject);
var
  WriteEPC:array[0..100] of Char;
  ENum:byte;
begin
  if Length(Edit_AccessCode3.Text)<8 then
  begin
     MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
    Exit;
  end;
  if (Length(Edit_WriteEPC.Text)mod 4<>0) then
  begin
  MessageDlg('Please input Data in words in hexadecimal form!'+#13+#10+'For example: 1234、12345678', mtInformation, [mbOK], 0);
  Exit;
  end;
   ENum:=Length(Edit_WriteEPC.text) div 4;
  getCharStr(Edit_WriteEPC.text,WriteEPC);
  getCharStr(Edit_AccessCode3.text,fPassword);
  fCmdRet:=WriteEPC_G2(fComAdr,@fPassword,@WriteEPC,ENum,ferrorcode,frmComPortindex);
  AddCmdLog('WriteEPC_G2', 'Wtite EPC', fCmdRet,ferrorcode);
  if fCmdRet=0 then
  begin
  StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Write EPC"Command Response=0x00' +
            '(Write EPC successfully)'
  end;
end;

procedure TfrmRRU9816main.Action_SetReadProtect_G2Execute(Sender: TObject);
var
  ENum:byte;
  MaskMem:Byte;
  MaskAdr:array[0..2]of Char;
  MaskLen:Byte;
  MaskData:array[0..80]of Char;
begin
    if(Edit2.Text='')then Exit;
    if(Edit3.Text='')then Exit;
    if(Edit1.Text='')or(Length(Edit1.Text)mod 2<>0)then Exit;
    if(R_EPC.Checked)then MaskMem:=1;
    if(R_TID.Checked)then MaskMem:=2;
    if(R_User.Checked)then MaskMem:=3;
    FillChar( MaskData,80,0);
    getCharStr(Edit2.Text,MaskAdr);
     MaskLen:=StrToInt('$'+trim(edit3.Text));
      getCharStr(Edit1.Text,MaskData);
  if Length(Edit_AccessCode4.Text)<8 then
  begin
    MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
    Exit;
  end;
   if(CheckBox1.Checked)then
    ENum:=255
   else
   ENum:=Length(ComboBox_EPC4.text)div 4;
  getCharStr(ComboBox_EPC4.text,fOperEPC);
  getCharStr(Edit_AccessCode4.text,fPassword);
  fCmdRet:=SetPrivacyByEPC_G2(fComAdr,@fOperEPC,ENum,@fPassword,MaskMem,@MaskAdr,MaskLen,@MaskData,ferrorcode,frmComPortindex);
  AddCmdLog('SetPrivacyByEPC_G2', 'Set PrivacyBy EPC', fCmdRet,ferrorcode);
  if fCmdRet=0 then
  begin
  StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Set PrivacyBy EPC"Command Response=0x00' +
            '(Set PrivacyBy EPC successfully)'
  end;
end;

procedure TfrmRRU9816main.Action_SetMultiReadProtect_G2Execute(
  Sender: TObject);
begin
  if Length(Edit_AccessCode4.Text)<8 then
  begin
    MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
    Exit;
  end;
  getCharStr(Edit_AccessCode4.text,fPassword);
  fCmdRet:=SetPrivacyWithoutEPC_G2(fComAdr,@fPassword,ferrorcode,frmComPortindex);
  AddCmdLog('SetPrivacyWithoutEPC_G2', 'Set Privacy Without EPC', fCmdRet,ferrorcode);
  if fCmdRet=0 then
  begin
  StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Set Privacy Without EPC"Command Response=0x00' +
            '(Set Privacy Without EPC successfully)'
  end;
end;

procedure TfrmRRU9816main.Action_RemoveReadProtect_G2Execute(
  Sender: TObject);
begin
  if Length(Edit_AccessCode4.Text)<8 then
  begin
   MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
    Exit;
  end;
  getCharStr(Edit_AccessCode4.text,fPassword);
  fCmdRet:=ResetPrivacy_G2(fComAdr,@fPassword,ferrorcode,frmComPortindex);
  AddCmdLog('ResetPrivacy_G2', 'ResetPrivacy', fCmdRet,ferrorcode );
  if fCmdRet=0 then
  begin
  StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  '"Reset Privacy"Command Response=0x00' +
            '(Reset Privacy successfully)'
  end;
end;

procedure TfrmRRU9816main.Action_CheckReadProtected_G2Execute(
  Sender: TObject);
var
  readpro:Byte;
begin
  fCmdRet:=CheckPrivacy_G2(fComAdr,readpro,ferrorcode,frmComPortindex);
  AddCmdLog('CheckPrivacy_G2', 'Check Privacy', fCmdRet);
  if fCmdRet=0 then
  begin
   if readpro=0 then
  StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Check Privacy"Command Response=0x00' +
            '(Single Tag is unprotected)';
   if readpro=1 then
  StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Check Privacy"Command Response=0x01' +
            '(Single Tag is protected)';
  end ;
end;

procedure TfrmRRU9816main.Action_SetEASAlarm_G2Execute(Sender: TObject);
var
  ENum:byte;
  EAS:Byte;
  MaskMem:Byte;
  MaskAdr:array[0..2]of Char;
  MaskLen:Byte;
  MaskData:array[0..80]of Char;
begin
  if(R_EPC.Checked)then MaskMem:=1;
  if(R_TID.Checked)then MaskMem:=2;
  if(R_User.Checked)then MaskMem:=3;
  FillChar( MaskData,80,0);
  if Length(Edit_AccessCode5.Text)<8 then
  begin
     MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
    Exit;
  end;
  if(CheckBox1.Checked)then
  begin
  ENum:=255;
   if(Edit2.Text='')then Exit;
   if(Edit3.Text='')then Exit;
   if(Edit1.Text='')or(Length(Edit1.Text)mod 2<>0)then Exit;
   getCharStr(Edit2.Text,MaskAdr);
   MaskLen:=StrToInt('$'+trim(edit3.Text));
   getCharStr(Edit1.Text,MaskData);
  end
  else
    ENum:=Length(ComboBox_EPC5.text) div 4;
  getCharStr(ComboBox_EPC5.text,fOperEPC);
  getCharStr(Edit_AccessCode5.text,fPassword);
  if Alarm_G2.checked then EAS:= $01
  else EAS:=$00;
  fCmdRet:=EASConfigure_G2(fComAdr,@fOperEPC,ENum,@fPassword,EAS,MaskMem,@MaskAdr,MaskLen,@MaskData,ferrorcode,frmComPortindex);
  AddCmdLog('EASConfigure_G2', 'EAS Configure', fCmdRet,ferrorcode);   //v2.1改
  if fCmdRet=0 then
  begin
   if Alarm_G2.checked then  //v2.1 add     
   StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "EAS Configure"Command Response=0x00' +
            '(Set EAS Alarm successfully)'                 //
   else
   StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "EAS Configure"Command Response=0x00' +
            '(Clear EAS Alarm successfully)'
  end;
end;

procedure TfrmRRU9816main.SpeedButton_CheckAlarm_G2Click(Sender: TObject);
begin
  if SpeedButton_CheckAlarm_G2.Down  then
  begin
    Timer_G2_Alarm.Enabled:=True;
  end
  else
  begin
    Timer_G2_Alarm.Enabled:=False;
    Label_Alarm.Visible:=False;                       //v2.1增加
    StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "EAS Alarm"over' ;
  end;
end;

procedure TfrmRRU9816main.Timer_G2_AlarmTimer(Sender: TObject);
var
  ENum:byte;
begin
  if  fTimer_G2_Alarm then    exit;
  fTimer_G2_Alarm:=true;
  try
    if SpeedButton_CheckAlarm_G2.Down  then
    begin
      fCmdRet:=EASAlarm_G2(fComAdr,ferrorcode,frmComPortindex);
      if fCmdRet=0 then
      begin
         StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "EAS Alarm"Command Response=0x00' +
                  '(EAS alarm detected)';
         Label_Alarm.Visible:=True;                       //v2.1增加
      end
      else
      begin
        Label_Alarm.Visible:=False;                       //v2.1增加
        AddCmdLog('EASAlarm_G2', 'EAS Alarm', fCmdRet);
      end;
      if not(SpeedButton_CheckAlarm_G2.Down)then
      begin
        Label_Alarm.Visible:=False;                       //v2.1增加
        StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  '"EAS Alarm"over' ;
      end;
    end;
  finally
    fTimer_G2_Alarm:=false;
  end;
  if fAppClosed then Close;
end;

procedure TfrmRRU9816main.Action_LockUserBlock_G2Execute(Sender: TObject);
var
  ENum:byte;
  BlockNum:Byte;
  MaskMem:Byte;
  MaskAdr:array[0..2]of Char;
  MaskLen:Byte;
  MaskData:array[0..80]of Char;
begin
  if(R_EPC.Checked)then MaskMem:=1;
  if(R_TID.Checked)then MaskMem:=2;
  if(R_User.Checked)then MaskMem:=3;
  FillChar( MaskData,80,0);
  if Length(Edit_AccessCode6.Text)<8 then
  begin
    MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
    Exit;
  end;
  if(CheckBox1.Checked)then
  begin
    ENum:=255 ;
    if(Edit2.Text='')then Exit;
    if(Edit3.Text='')then Exit;
    if(Edit1.Text='')or(Length(Edit1.Text)mod 2<>0)then Exit;
    getCharStr(Edit2.Text,MaskAdr);
    MaskLen:=StrToInt('$'+trim(edit3.Text));
    getCharStr(Edit1.Text,MaskData);
  end
  else
  ENum:=Length(ComboBox_EPC6.text) div 4;
  getCharStr(ComboBox_EPC6.text,fOperEPC);
  getCharStr(Edit_AccessCode6.text,fPassword);
  BlockNum:=ComboBox_BlockNum.itemindex*2 ;
  fCmdRet:=BlockLock_G2(fComAdr,@fOperEPC,ENum,@fPassword,BlockNum,MaskMem,@MaskAdr,MaskLen,@MaskData,ferrorcode,frmComPortindex);
  AddCmdLog('BlockLock_G2', 'BlockLock_G2', fCmdRet,ferrorcode);
  if fCmdRet=0 then
  begin
  StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "BlockLock"Command Response=0x00' +
            '(BlockLock successfully)'
  end;
end;

procedure TfrmRRU9816main.PageControl1Change(Sender: TObject);
begin
  if (PageControl1.ActivePage <> TabSheet_EPCC1G2) then
  begin
    Timer_Test_.Enabled := False;
    SpeedButton_Query.Down:=False;
    SpeedButton_CheckAlarm_G2.Down:=False;
    SpeedButton_Read_G2.Down:=False;
    Timer_G2_Alarm.Enabled:=False;
    Timer_G2_Read.Enabled:=False;
    SpeedButton_Write_6B.Down:=False;
    SpeedButton_Read_6B.Down:=False;
  end;
  if (PageControl1.ActivePage <> TabSheet_6B) then
  begin
    Timer_Test_6B.Enabled := False;
    SpeedButton_Query_6B.Down:=False;
  end;
  breakflag:=False;
  if (PageControl1.ActivePage <> TabSheet3) then
  begin
    breakflag:=True;
    Button21.Enabled:=ComIsOpen;
    Button23.Enabled:=False;
  end;

  if (PageControl1.ActivePage <> TabSheet2)then
    begin
      Timer1.Enabled:=False;
      btStartBuffer.Caption:='Start';
    end;
    btStartBuffer.Enabled:=ComIsOpen;
    btGetBuffer.Enabled:=ComIsOpen;
    btClearBuffer.Enabled:=ComIsOpen;
    btGetAndClBuffer.Enabled:=ComIsOpen;
    btGetBufferNum.Enabled:=ComIsOpen;
end;

procedure TfrmRRU9816main.Button_BeepClick(Sender: TObject);
var
  BeepEn:byte;
begin
 if(Radio_beepEn.Checked)then
  BeepEn:=1
 else
  BeepEn:=0;
 fCmdRet:=SetBeepNotification(fComAdr,BeepEn,frmComPortindex);
 AddCmdLog('SetBeepNotification', 'Set', fCmdRet);
end;

procedure TfrmRRU9816main.Edit8KeyPress(Sender: TObject; var Key: Char);
  var L:Boolean;
begin
   L:=(key<#8)or(key>#8)and(key<#48)or(key>#57) ;
    if l then key:=#0;
end;
function TfrmRRU9816main.getNoStr(no: Integer; noLen: Integer): string;
begin
  result := intToStr(no);
  while Length(result) < noLen do
    result := '0' + result;
end;
procedure TfrmRRU9816main.Button_clearBufferClick(Sender: TObject);
begin
fCmdRet:=ClearTagBuffer(fcomadr,frmcomportindex);
AddCmdLog('ClearTagBuffer', 'ClearTagBuffer', fCmdRet);
end;

procedure TfrmRRU9816main.Button_SetGPIOClick(Sender: TObject);
var
  OutputPin:Byte;
begin
  OutputPin:=0;
  if(CheckBox2.Checked)then
    OutputPin:=OutputPin or $01;
  if(CheckBox3.Checked)then
    OutputPin:=OutputPin or $02;
  fCmdRet:=SetGPIO(fcomadr,OutputPin,frmcomportindex);
  AddCmdLog('SetGPIO', 'Set', fCmdRet);
end;

procedure TfrmRRU9816main.Button_GetGPIOClick(Sender: TObject);
var
  OutputPin:Byte;
begin
  OutputPin:=0;
  fCmdRet:=GetGPIOStatus(fcomadr,OutputPin,frmcomportindex);
  if(fCmdRet=0)then
  begin

    if(OutputPin and $01)=$01then
     CheckBox6.Checked:=True
    else
     CheckBox6.Checked:=False;
    if(OutputPin and $02)=$02then
     CheckBox4.Checked:=True
    else
     CheckBox4.Checked:=False;

    if(OutputPin and $10)=$10then
     CheckBox2.Checked:=True
    else
     CheckBox2.Checked:=False;
    if(OutputPin and $20)=$20then
     CheckBox3.Checked:=True
    else
     CheckBox3.Checked:=False;
  end;
  AddCmdLog('GetGPIO', 'Get', fCmdRet);
end;

Function TfrmRRU9816main.Str_IntToBin(Int: LongInt; Size: Integer): String;
Var
  i: Integer;
Begin
  Result:='';
  If Size < 1 Then Exit;
  For i := Size Downto 1 Do
    Begin
      If Int And (1 Shl (Size - i)) <> 0 Then
        Result := '1' + Result
      Else
        Result := '0' + Result;
    End;
End;
function TfrmRRU9816main.BitStrToHextStr(const BitStr: String): String;
var
  vD : Byte;
  I : Integer;
  vHextStr : String;
  vP : PChar;
  vLen : Integer;
begin
  vLen := Length(BitStr);
  if vLen mod 4 > 0 then
  begin
      SetLength(vHextStr,   vLen   div   4   +   1);
      vLen := vlen div 4 + 1;
  end
  else
  begin
      SetLength(vHextStr,   vLen   div   4);
      vLen := vlen div 4 ;
  end;
  //初始化
  vD := 0;
  vP := PChar(BitStr)+length(BitStr)-1;
  I := 0;   //开始计数
  while vP^ <> #0 do
  begin
      if vp^ = '1' then
      begin
        case i of
          0:    vD :=vd+1;
          1:    vD :=vd+2;
          2:    vD :=vd+4;
          3:    vD :=vd+8;
        end;
      end;
      Dec(vP);
      Inc(I);
      if I = 4 then
      begin
        case vD of
          0..9 : vHextStr[vLen] := Chr(vD + $30);
          10..15 : vHextStr[vLen] := Chr(vD - 10 + $41);
        end;
        Dec(vLen);
        I :=   0;
        vD :=   0;
      end;
  end;
  if I > 0then
  begin
      case   vD   of
        0..9 : vHextStr[vLen] := Chr(vD + $30);
        10..15 : vHextStr[vLen] := Chr(vD + $41);
      end;
  end;
  Result := vHextStr;
end;
procedure TfrmRRU9816main.ComboBox_dminfreSelect(Sender: TObject);
begin
  if CheckBox_SameFre.Checked then
    begin
      if TComboBox(Sender).Tag=1 then
      ComboBox_dminfre.ItemIndex:=ComboBox_dmaxfre.ItemIndex
      else
      ComboBox_dmaxfre.ItemIndex:=ComboBox_dminfre.ItemIndex;
    end
  else if  ComboBox_dminfre.ItemIndex> ComboBox_dmaxfre.ItemIndex  then
  begin
    if TComboBox(Sender).Tag=0 then
    ComboBox_dminfre.ItemIndex:=ComboBox_dmaxfre.ItemIndex
    else
    ComboBox_dmaxfre.ItemIndex:=ComboBox_dminfre.ItemIndex;
    Application.MessageBox('Min.Frequency is equal or lesser than Max.Frequency', 'Error Information', MB_ICONINFORMATION);
  end;
end;

procedure TfrmRRU9816main.Button16Click(Sender: TObject);
begin
 Memo_DataShow.Lines.Clear;
end;

procedure TfrmRRU9816main.Button21Click(Sender: TObject);
var
  dminfre, dmaxfre,Ffenpin:Byte;
  i,j,ncount:Integer;
  CardNum:Integer;
  Totallen,UID_index,n_index:Integer;
  EPC: array[0..5000] of Char;
  temp1,temp2,temp3,temp4:string;
  MaskMem:Byte;
  MaskAdr:array[0..2]of Char;
  MaskLen:Byte;
  MaskData:array[0..80]of Char;
  MaskFlag:Byte;
  Ant,Qvalue,Session:Byte;
   AdrTID,LenTID,TIDFlag:Byte;
begin
  Button21.Enabled:=False;
  Button23.Enabled:=True;
  ListBox1.Items.Clear;
  AdrTID:=0;
  LenTID:=0;
  TIDFlag:=0;
  Qvalue:=Com_Q.ItemIndex;
  Session:=Com_S.ItemIndex;
  for  Ffenpin:=0 to 49 do
  begin
   Application.ProcessMessages;
   if(breakflag=True)then
   begin
   breakflag:=False;
   if fAppClosed then Close;
   Exit;
   end;
   dminfre := ((2 and 3)shl 6)or (Ffenpin and $3F) ;
   dmaxfre := ((2 and $c)shl 4)or (Ffenpin and $3F) ;
   y_f:=902.75+(Ffenpin and $3F)*0.5;
   temp4:=Format('%f',[y_f,0]);
   temp3:=temp4+'MHz'+'('+Format('%-2d',[Ffenpin])+')';
  // ListBox1.Items.Add(Format('%-4d',[Ffenpin]));
   ListBox1.Items.Add(temp3);
   for i:=0 to 3 do
   begin
   fCmdRet := SetRegion(fComAdr,dmaxfre,dminfre,frmcomportindex);
   if(fCmdRet=0)then
   Break;
   end;
   ncount:=0;
   for j:=0 to 29 do
   begin
     Application.ProcessMessages;
     if(breakflag)then
     begin
     breakflag:=False;
     if fAppClosed then Close;
     Exit;
     end;
     CardNum:=0;
     MaskFlag:=0 ;
     fCmdRet :=Inventory_G2(fComAdr,Qvalue,Session,MaskMem,@MaskAdr,MaskLen,@MaskData,MaskFlag, AdrTID,LenTID,TIDFlag,Target,InAnt,Scantime,FastFlag,@EPC,Ant,Totallen,CardNum,frmcomportindex);
     if(fCmdRet=1) or(fCmdRet=2) or(fCmdRet=3)or(fCmdRet=4)  then
     begin
        ncount:=ncount+1;
        if(ncount=1)then
        UID_index := ListBox1.Items.IndexOf(temp3)
        else
        UID_index := ListBox1.Items.IndexOf(temp3+'            '+Format('%-2d',[ncount-1])+'/30');
        if UID_index>=0 then
        begin
          ListBox1.Items[UID_index] := temp3+'            '+Format('%-2d',[ncount])+'/30';
        end;
     end;
   end;
   if(ncount=0)then
   begin
      UID_index := ListBox1.Items.IndexOf(temp3);
      if UID_index>=0 then
      begin
        ListBox1.Items[UID_index] := temp3+'            '+Format('%-2d',[ncount])+'/30'+'                  '+'00.00%';
      end;
   end;
    UID_index := ListBox1.Items.IndexOf(temp3+'            '+Format('%-2d',[ncount])+'/30');
    if UID_index>=0 then
    begin
      x_z:=ncount/30*100;
      temp1:= FloatToStr(x_z);
      if(ncount=30)then
      temp2:='100.00%'
      else
      begin
         n_index:=Pos('.',temp1); //
       if(n_index>0)then
        temp2:=Copy(temp1,1,n_index-1)+'.'+copy(temp1,n_index+1,2)+'%'
       else
        temp2:= temp1+'.'+'00'+'%';
      end;
      ListBox1.Items[UID_index] := temp3+'            '+Format('%-2d',[ncount])+'/30'+'                  '+temp2;
    end;
    ListBox1.ItemIndex:=ListBox1.Items.Count-1;
  end;
  Button21.Enabled:=True;
  Button23.Enabled:=False;
end;

procedure TfrmRRU9816main.Button23Click(Sender: TObject);
begin
 breakflag:=True;
 Button21.Enabled:=True;
 Button23.Enabled:=False;
end;

procedure TfrmRRU9816main.Button24Click(Sender: TObject);
begin
ListBox1.Items.Clear;
end;

procedure TfrmRRU9816main.ComboBox_COMChange(Sender: TObject);
begin
  ComboBox_baud2.Items.Clear;
  if(ComboBox_COM.ItemIndex=0)then
  begin
    ComboBox_baud2.Items.Add('9600bps');
    ComboBox_baud2.Items.Add('19200bps');
    ComboBox_baud2.Items.Add('38400bps');
    ComboBox_baud2.Items.Add('57600bps');
    ComboBox_baud2.Items.Add('115200bps');
    ComboBox_baud2.ItemIndex:=3;
  end
  else
  begin
    ComboBox_baud2.Items.Add('Auto');
    ComboBox_baud2.ItemIndex:=0;
  end;
end;


procedure TfrmRRU9816main.xxit1Click(Sender: TObject);
begin
Close;
end;

procedure TfrmRRU9816main.FormCloseQuery(Sender: TObject;
  var CanClose: Boolean);
begin

  breakflag:=True;
  fAppClosed:=True;
end;

procedure TfrmRRU9816main.CheckBox_TIDClick(Sender: TObject);
begin
  if(CheckBox_TID.Checked)then
  begin
  Edit13.Enabled:=True;
  Edit14.Enabled:=True;
  end
  else
  begin
  Edit13.Enabled:=False;
  Edit14.Enabled:=False;
  end;
end;



procedure TfrmRRU9816main.Edit_WriteDataChange(Sender: TObject);
var
  m,n:Integer;
begin
    n:= Length(Trim(Edit_WriteData.Text));
    if(CheckBox18.Checked)and(n mod 4=0)and(C_EPC.Checked)then
    begin
      m:=n div 4;
      m:=(m and $3F) shl 3;
      Edit_PC.Text:=IntToHex(m,2)+'00';
    end;
end;

procedure TfrmRRU9816main.CheckBox18Click(Sender: TObject);
var
  m,n:Integer;
begin
  if(CheckBox18.Checked)then
  begin
    Edit_WordPtr.Text:='0002';
    Edit_WordPtr.ReadOnly:=True;
    n:= Length(Trim(Edit_WriteData.Text));
    if(CheckBox18.Checked)and(n mod 4=0)and(C_EPC.Checked)then
    begin
      m:=n div 4;
      m:=(m and $3F) shl 3;
      Edit_PC.Text:=IntToHex(m,2)+'00';
    end;

  end
  else
  begin
    Edit_WordPtr.ReadOnly:=False;;
  end;
end;

procedure TfrmRRU9816main.C_ReserveClick(Sender: TObject);
begin
Edit_WordPtr.ReadOnly:=False;
end;

procedure TfrmRRU9816main.C_TIDClick(Sender: TObject);
begin
  Edit_WordPtr.ReadOnly:=False;
end;

procedure TfrmRRU9816main.C_UserClick(Sender: TObject);
begin
Edit_WordPtr.ReadOnly:=False;
end;

procedure TfrmRRU9816main.C_EPCClick(Sender: TObject);
begin
 if CheckBox18.Checked then
  begin
    Edit_WordPtr.ReadOnly:=True;
    Edit_WordPtr.Text:='0002';
  end
  else
  begin
   Edit_WordPtr.ReadOnly:=False;
  end;
end;

procedure TfrmRRU9816main.Button31Click(Sender: TObject);
var
  ATMode:Byte;
begin
  ATMode:=0;
  SeriaATflag:=False;
  fCmdRet:=ChangeATMode(fComAdr,ATMode,frmComPortindex);
  if(fCmdRet<>0)then
  begin
    SeriaATflag:=True;
  end;
  AddCmdLog('ChangeATMode', 'EXIT', fCmdRet);
end;

procedure TfrmRRU9816main.Button34Click(Sender: TObject);
var
  timeout:Byte;
  nlen:Byte;
  cmddata:array[0..100]of Char;
  recvLen:Byte;
  recvdata:array[0..1000]of Char;
  i,q,m,n:Integer;
  cmd,recv,code:string;
begin
  cmd:='AT!S';
  q:= Length(cmd);
  move(cmd[1],cmddata,q);
  nlen:=q+2;
  cmddata[q]:=Char(13);
  cmddata[q+1]:=Char(10);
  timeout:=30;
  FillChar(recvdata,1000,0);
  fCmdRet:=TransparentCMD(fComAdr,timeout,nlen,cmddata,recvLen,recvdata,frmComPortindex);
  if(fCmdRet=0)then
  begin
   recv:=strpas(recvdata);
   if(Pos('ERROR',recv)>0)or(recvLen=0)then
   begin
      MessageDlg('Set failed', mtWarning, [mbOK], 0);
      Exit;
   end;
  end;
  AddCmdLog('TransparentCMD', 'Set', fCmdRet);
  Sleep(500);
  cmd:='AT!R';
  q:= Length(cmd);
  move(cmd[1],cmddata,q);
  nlen:=q+2;
  cmddata[q]:=Char(13);
  cmddata[q+1]:=Char(10);
  timeout:=30;
  FillChar(recvdata,1000,0);
  fCmdRet:=TransparentCMD(fComAdr,timeout,nlen,cmddata,recvLen,recvdata,frmComPortindex);
  if(fCmdRet=0)then
  begin
   recv:=strpas(recvdata);
   if(Pos('ERROR',recv)>0)or(recvLen=0)then
   begin
      MessageDlg('Set failed', mtWarning, [mbOK], 0);
      Exit;
   end;
  end;
  AddCmdLog('TransparentCMD', 'Set', fCmdRet);
end;

procedure TfrmRRU9816main.Button8Click(Sender: TObject);
var
  SeriaNo:array[0..4]of Char;
  temp:string;
begin
  fCmdRet:=GetSeriaNo(fComAdr,SeriaNo,frmComPortindex);
  if(fCmdRet=0)then
  begin
    temp:=getStr(SeriaNo,4);
    Edit15.Text:=getHexStr(temp);
  end;
  AddCmdLog('GetSeriaNo', 'Get', fCmdRet);
end;

procedure TfrmRRU9816main.Action_Inventroy_6BExecute(Sender: TObject);
procedure ChangeSubItem1(aListItem: TListItem; subItemIndex: Integer; ItemText: string;ant1,RSSI:string);
  begin
    if aListItem.SubItems[subItemIndex] = ItemText then
    begin
      if(aListItem.SubItems[1]='')then
      begin
         aListItem.SubItems[1]:=ant1;
      end
      else
      begin
         aListItem.SubItems[1]:=Str_IntToBin(StrToInt('$'+BitStrToHextStr(aListItem.SubItems[1]))or StrToInt('$'+BitStrToHextStr(ant1)),4) ;
      end;
      if (aListItem.SubItems[2]='99999') or (aListItem.SubItems[2]='')then              //aListItem.SubItems[2]为次数
       aListItem.SubItems[2]:='0'                        //aListItem.SubItems[0]为 EPC号
      else
      begin
       aListItem.SubItems[2]:= IntToStr(StrToInt(aListItem.SubItems[2])+1);
       aListItem.SubItems[3]:=RSSI;
       exit; //内容相同则不需要修改，可以不闪烁
      end;
    end;
     aListItem.SubItems[1]:=ant1;
    aListItem.SubItems[2]:='1';
    aListItem.SubItems[3]:=RSSI;
    aListItem.SubItems[subItemIndex] := ItemText;

  end;
   procedure ChangeSubItem2(aListItem: TListItem; subItemIndex: Integer; ItemText,RSSI: string);
  begin
    if aListItem.SubItems[subItemIndex] = ItemText then         //aListItem.SubItems[1]为 EPC长度
    exit; //内容相同则不需要修改，可以不闪烁
    aListItem.SubItems[subItemIndex] := ItemText;
  end;
var
  CardNum:Integer;
  EPClen,m,Totallen:Integer;
  ID_6B: array[0..2000] of Char;
  ID2_6B: array[0..5000] of Char;
  isonstring:Boolean;
  isonlistview:Boolean;
  CardIndex: Integer;
  temps: string;
  s,ss, sID: string;
  aListItem: TListItem;
  RSSI,temps2, temps3: string;
  i, j: integer;
  Condition,Ant:Byte;
  StartAddress,mask:Byte;
  ConditionContent:array[0..300] of Char;
  Contentlen:Byte;

begin
  fIsInventoryScan_6B := true;
  try
    if Byone_6B.Checked then
    begin
    fCmdRet :=InventorySingle_6B(fComAdr,Ant,@ID_6B,frmcomportindex);
      if  fCmdRet = $00  then 
      begin
        temps :=getStr(ID_6B,10);                                                       //屏蔽
        s := getHexStr(temps);
        RSSI:= Copy(s,19,2);
        s:=Copy(s,3,16);

        RSSI:= IntToStr(StrToInt('$'+RSSI));
        isonlistview:=False;
        for i:=1 to ListView_ID_6B.Items.Count do      //判断是否在Listview列表内
        begin
          if s=(ListView_ID_6B.Items[i - 1]).SubItems[0] then
          begin
           aListItem := ListView_ID_6B.Items[i - 1];
           isonlistview:=True;
          end;
        end;
        if (not isonlistview) then
        begin
          aListItem := ListView_ID_6B.Items.Add;
          aListItem.Caption := IntToStr(aListItem.Index + 1);
          aListItem.SubItems.Add('');
          aListItem.SubItems.Add('');
          aListItem.SubItems.Add('');
          aListItem.SubItems.Add('');
          aListItem.SubItems.Add('');
          aListItem.SubItems.Add('');
          aListItem := ListView_ID_6B.Items[ListView_ID_6B.Items.Count - 1];
          ComboBox_ID1_6B.Items.Add(s);
        end;
        ChangeSubItem1(aListItem, 0,s, Str_IntToBin(Ant,4),RSSI);
        ComboBox_ID1_6B.Itemindex:=0;
      end;
    end

    else if Bycondition_6B.Checked then
    begin
      if  Same_6B.Checked then
      Condition:=$00
      else if Different_6B.Checked then
      Condition:=$01
      else if Greater_6B.Checked  then
      Condition:=$02
      else if Less_6B.Checked then
      Condition:=$03;
      ss:=Edit_ConditionContent_6B.text;
      Contentlen:=Length(Edit_ConditionContent_6B.text) ;
      for i:=1 to 16-Contentlen do
      ss:=ss+'0';
      getCharStr(ss,ConditionContent);
      case (Contentlen div 2) of
        1: mask:=$80;
        2: mask:=$C0;
        3: mask:=$E0;
        4: mask:=$F0;
        5: mask:=$F8;
        6: mask:=$FC;
        7: mask:=$FE;
        8: mask:=$FF;
      end;
      StartAddress:= StrToInt(Edit_Query_StartAddress_6B.Text);
//      mask:=StrToInt('$'+Edit_mask_6B.Text);
      fCmdRet :=InventoryMultiple_6B(fComAdr,Condition,StartAddress,mask,@ConditionContent,Ant,@ID2_6B,Cardnum,frmcomportindex);

      if  (fCmdRet = $15)or (fCmdRet = $16)or (fCmdRet = $17)or (fCmdRet = $18)or(fCmdRet = $FB)    then
      begin
         temps :=getStr(ID2_6B,Cardnum*10);
          fInventory_EPC_List := tempS;            //存贮记录
          m:=1;
          for CardIndex := 1 to CardNum do
          begin
              sID := copy(tempS,m,10) ;
              m:=m+10;
              if Length(sID) <> 10 then Continue;
              s := getHexStr(sID);
              RSSI:= Copy(s,19,2);
              s:=Copy(s,3,16);
              RSSI:= IntToStr(StrToInt('$'+RSSI));
            isonlistview:=False;
            for i:=1 to ListView_ID_6B.Items.Count do      //判断是否在Listview列表内
            begin
              if copy(s, 1, Length(s))=(ListView_ID_6B.Items[i - 1]).SubItems[0] then
              begin
               aListItem := ListView_ID_6B.Items[i - 1];
               isonlistview:=True;
              end;
            end;  
            if (not isonlistview) then
            begin
              aListItem := ListView_ID_6B.Items.Add;
              aListItem.Caption := IntToStr(aListItem.Index + 1);
              aListItem.SubItems.Add('');
              aListItem.SubItems.Add('');
              aListItem.SubItems.Add('');
              aListItem.SubItems.Add('');
              aListItem.SubItems.Add('');
              aListItem.SubItems.Add('');
              aListItem := ListView_ID_6B.Items[ListView_ID_6B.Items.Count - 1];
              ComboBox_ID1_6B.Items.Add(copy(s, 1, Length(s)));
            end;
            ChangeSubItem1(aListItem, 0,s, Str_IntToBin(Ant,4),RSSI);
            ComboBox_ID1_6B.Itemindex:=0;
          end;
      end;
    end;
  //        if ByEffect_6B.Checked  then
//          ListView_ID_6B.Clear;
    if Timer_Test_6B.Enabled then
    begin
      if Bycondition_6B.Checked then
      begin
        if  fCmdRet<>0 then
       AddCmdLog('Inventory', 'Query tag', fCmdRet);
      end
      else if fCmdRet = $FB then //说明还未将所有卡读取完
      begin

          StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) + ' "Query Tag"Command Response=0xFB' +
               '(No Tag Operable)'
      end
      else if fCmdRet = $00 then
         StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Query Tag"Command Response=0x00' +
               '(Find a Tag)'
      else
        AddCmdLog('Inventory', 'Query Tag', fCmdRet);
      if fCmdRet=RecmdErr then
       StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Query Tag"Command Response=0xee' +
                    '(Response Command Error)' ;
    end;
  finally
     fIsInventoryScan_6B := False;
  end;
  if fAppClosed then Close;
end;

procedure TfrmRRU9816main.Action_Query_6BExecute(Sender: TObject);
var
   i:   Integer;
begin
    if not (SpeedButton_Query_6B.down) then
    begin
       AddCmdLog('Inventory', 'Exit query', 0);
      Timer_Test_6B.Enabled:=False;
    end
    else
    begin
      if Bycondition_6B.Checked then
      begin
        if (Edit_Query_StartAddress_6B.Text='') or (Edit_ConditionContent_6B.Text='') then
        begin
          MessageDlg('Start address or condition is empty!Please input!', mtInformation, [mbOK], 0);
          SpeedButton_Query_6B.down:=False;
          Exit;
        end;
      end;
      Timer_Test_6B.Enabled:=True;
      ListView_ID_6B.Clear;
      ComboBox_ID1_6B.Clear;
    end;
end;

procedure TfrmRRU9816main.Action_LockByte_6BExecute(Sender: TObject);
var
   return,Address:Byte;
begin
   getCharStr(ComboBox_ID1_6B.text,fOperID_6B);
   Address:=StrToInt('$'+Edit_StartAddress_6B.Text);
   return:=MessageDlg('permanently Lock the address Confirmed？', mtInformation, [mbOK, mbCancel], 0);
   if return = IDCancel then
   Exit;
   fCmdRet:=Lock_6B(fComAdr,@fOperID_6B,Address,ferrorcode,frmComPortindex);
   AddCmdLog('Lock', 'Lock', fCmdRet);
end;

procedure TfrmRRU9816main.Action_CheckLock_6BExecute(Sender: TObject);
var
Address,ReLockState:Byte;
begin
   getCharStr(ComboBox_ID1_6B.text,fOperID_6B);
   Address:=StrToInt('$'+Edit_StartAddress_6B.Text);
   fCmdRet:=CheckLock_6B(fComAdr,@fOperID_6B,Address,ReLockState,ferrorcode,frmComPortindex);
  AddCmdLog('CheckLock_6B', 'Check Lock', fCmdRet);
   if fCmdRet=0 then
   begin
     if  ReLockState=$00  then
     StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Check Lock"Command Response=0x00' +
               '(The Byte is unlocked)' ;
     if  ReLockState=$01  then
     StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Check Lock"Command Response=0x01' +
               '(The Byte is locked)';

   end;
end;

procedure TfrmRRU9816main.Action_CheckLock_6BUpdate(Sender: TObject);
var
  CanEnabled_6B:Boolean;
  CanEnabled2_6B:Boolean;
begin
    SpeedButton_Query_6B.Enabled:=ComIsOpen and not (SpeedButton_Read_6B.down)
                                   and not (SpeedButton_Write_6B.down);
    ComboBox_IntervalTime_6B.Enabled:=not (SpeedButton_Query_6B.down) and  ComIsOpen
                   and not (SpeedButton_Read_6B.down)and not (SpeedButton_Write_6B.down);
    CanEnabled_6B:=not (SpeedButton_Query_6B.down) and  ComIsOpen and (ComboBox_ID1_6B.Text<>'')
                   and not (SpeedButton_Read_6B.down)and not (SpeedButton_Write_6B.down);
    CanEnabled2_6B:=not (SpeedButton_Query_6B.down) and  ComIsOpen and (Bycondition_6B.Checked)
                   and not (SpeedButton_Read_6B.down)and not (SpeedButton_Write_6B.down);
    if  Byone_6B.Checked then
     SpeedButton_Query_6B.Caption:='Query by one'
    else
    begin
     SpeedButton_Query_6B.Caption:='Query by Condition';
    end;
     GroupBox14.Enabled:=CanEnabled2_6B;
    Label34.Enabled:=CanEnabled2_6B;
    Label28.Enabled:=CanEnabled2_6B;
    Edit_Query_StartAddress_6B.Enabled:=CanEnabled2_6B;
    Edit_ConditionContent_6B.Enabled:=CanEnabled2_6B;
    Less_6B.Enabled:=CanEnabled2_6B;
    Different_6B.Enabled:=CanEnabled2_6B;
    Same_6B.Enabled:=CanEnabled2_6B;
    Greater_6B.Enabled:=CanEnabled2_6B;

    GroupBox13.Enabled:=not (SpeedButton_Query_6B.down) and  ComIsOpen
                        and (ComboBox_ID1_6B.Text<>'');
    Memo_DataShow_6B.Enabled:=GroupBox13.Enabled;
    Button11.Enabled:=GroupBox13.Enabled;
    SpeedButton_Read_6B.Enabled:=GroupBox13.Enabled and not (SpeedButton_Write_6B.down);
    SpeedButton_Write_6B.Enabled:=GroupBox13.Enabled and not (SpeedButton_Read_6B.down);

    Label29.Enabled:=CanEnabled_6B;
    Label30.Enabled:=CanEnabled_6B;
    Label31.Enabled:=CanEnabled_6B;
    ComboBox_ID1_6B.Enabled:=CanEnabled_6B;
    Edit_WriteData_6B.Enabled:=CanEnabled_6B;
    Edit_StartAddress_6B.Enabled:=CanEnabled_6B;
    Edit_Len_6B.Enabled:=CanEnabled_6B;
    Button7.Enabled:=CanEnabled_6B;
    Button10.Enabled:=CanEnabled_6B;
end;

procedure TfrmRRU9816main.SpeedButton_Read_6BClick(Sender: TObject);
begin
     if SpeedButton_Write_6B.Down  then
    begin
    if ( Edit_WriteData_6B.Text='' )or (Length(Edit_WriteData_6B.Text)mod 2<>0) then
    begin
    MessageDlg('Please input in bytes in hexadecimal form!'+#13+#10+'for example: 12、1234', mtInformation, [mbOK], 0);
    SpeedButton_Write_6B.Down:=False;
    Exit;
    end;
    end;
    if SpeedButton_Read_6B.Down or SpeedButton_Write_6B.Down  then
    begin
    if ( Edit_StartAddress_6B.Text='' )or (Edit_Len_6B.Text='') then
    begin
    MessageDlg('Start address or length is empty!Please input!', mtInformation, [mbOK], 0);
    SpeedButton_Read_6B.Down:=False;
    SpeedButton_Write_6B.Down:=False;
    Exit;
    end;
    Timer_6B_ReadWrite.Enabled:=True;
    end
    else
    begin
    if Sender= SpeedButton_Read_6B  then
    StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Read"over' ;
    if Sender= SpeedButton_Write_6B  then
    StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Write"over' ;
    Timer_6B_ReadWrite.Enabled:=False;
    end;
end;

procedure TfrmRRU9816main.Button11Click(Sender: TObject);
begin
Memo_DataShow_6B.Clear;
end;

procedure TfrmRRU9816main.ComboBox_IntervalTime_6BChange(Sender: TObject);
begin
Timer_Test_6B.Interval :=(ComboBox_IntervalTime_6B.ItemIndex+4)*10;
end;

procedure TfrmRRU9816main.Timer_Test_6BTimer(Sender: TObject);
begin
    if fisinventoryscan_6B then    Exit;
    Action_Inventroy_6BExecute(sender);
end;

procedure TfrmRRU9816main.Timer_6B_ReadWriteTimer(Sender: TObject);
var
    i: Integer;
    s2: string;
    CardData: array[0..320] of Char;
    Mem,Num,StartAddress:Byte;
    Writedata:array[0..320] of Char;
    Writedatalen:byte;
    writtenbyte:longint;
begin
  if  fTimer_6B_ReadWrite then    exit;
  fTimer_6B_ReadWrite:=true;
  try

    if SpeedButton_Read_6B.Down  then
    begin
      getCharStr(ComboBox_ID1_6B.text,fOperID_6B);
      StartAddress:=StrToInt('$'+Edit_StartAddress_6B.Text);
      Num:=StrToInt(Edit_Len_6B.Text);
      fCmdRet:=ReadData_6B(fComAdr,@fOperID_6B,StartAddress,Num,CardData,ferrorcode,frmComPortindex);
      if fCmdRet=0 then
      begin
        for i := 0 to Num - 1 do
        s2 := s2 + IntToHex(ord(CardData[i]), 2);
        Memo_DataShow_6B.Lines.Add(s2);
      end;
      AddCmdLog('ReadData_6B', 'Read', fCmdRet);
      if not (SpeedButton_Read_6B.Down)  then
      StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  ' "Read"over' ;
    end;
    
    if SpeedButton_Write_6B.Down  then
    begin
      getCharStr(ComboBox_ID1_6B.text,fOperID_6B);
      StartAddress:=StrToInt('$'+Edit_StartAddress_6B.Text);
      getCharStr(Edit_WriteData_6B.text,Writedata);
      Writedatalen:= Length(Edit_WriteData_6B.text)div 2 ;
      fCmdRet:=WriteData_6B(fComAdr,@fOperID_6B,StartAddress,Writedata,Writedatalen,writtenbyte,ferrorcode,frmComPortindex);
      AddCmdLog('WriteData_6B', 'Write', fCmdRet);
      if not (SpeedButton_Write_6B.Down)  then
      StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +  '  "Write"over' ;
    end;
  finally
  fTimer_6B_ReadWrite:=false;
  end;
  if fAppClosed then Close;
end;

procedure TfrmRRU9816main.bt_setlenClick(Sender: TObject);
var
  SaveLen:Byte;
begin
  SaveLen:= 0;
  if(rb_128.Checked)then
      SaveLen := 0
  else
      SaveLen := 1;
  fCmdRet:= SetSaveLen(fComAdr, SaveLen, frmcomportindex);
  AddCmdLog('SetSaveLen','Set',fCmdRet);
end;

procedure TfrmRRU9816main.bt_getlenClick(Sender: TObject);
var
  SaveLen:Byte;
begin
  SaveLen := 0;
  fCmdRet := GetSaveLen(fComAdr,SaveLen, frmcomportindex);
  if (fCmdRet = 0)then
  begin
      if (SaveLen = 0)then
          rb_128.Checked := true
      else
          rb_496.Checked := true;
  end;
  AddCmdLog('GetSaveLen','Get',fCmdRet);
end;

procedure TfrmRRU9816main.btStartBufferClick(Sender: TObject);
begin
 Timer1.Enabled:= not Timer1.Enabled;
  if(Timer1.Enabled)then
  begin
    btStartBuffer.Caption:='Stop';
  end
  else
  begin
    btStartBuffer.Caption:='Start';
  end;
end;

procedure TfrmRRU9816main.btGetBufferClick(Sender: TObject);
var
  pEPCList:array[0..30000]of Char;
  Totallen,CardNum,CardIndex,EPClen,m:LongInt;
  temps,sEPC,s,s2,RSSI,ANTstr,strcount:string;
  aListItem: TListItem;
begin
  Totallen:=0;
  CardNum:=0;
  lb_Num.Caption:='0';
  ListView1.Items.Clear;
  fCmdRet:=ReadBuffer_G2(fComAdr, Totallen,CardNum,pEPCList, frmcomportindex);
  AddCmdLog('ReadBuffer_G2','Read Buffer',fCmdRet);
  if(fCmdRet=1)then
  begin
    temps :=getStr(pEPCList,Totallen);
    m:=1;
    for CardIndex := 1 to CardNum do
    begin
      ANTstr:=IntToStr(ord(tempS[m]));
      EPClen:=ord(tempS[m+1]);
      sEPC := copy(tempS,m+2,EPClen) ;
      s := getHexStr(sEPC);
      RSSI:= IntToStr(ord(tempS[m+2+EPClen]));
      strcount:=IntToStr(ord(tempS[m+3+EPClen]));
      m:=m+4+ EPClen;
      aListItem := ListView1.Items.Add;
      aListItem.Caption := IntToStr(aListItem.Index + 1);
      aListItem.SubItems.Add('');
      aListItem.SubItems.Add('');
      aListItem.SubItems.Add('');
      aListItem.SubItems.Add('');
      aListItem.SubItems.Add('');
      aListItem.SubItems.Add('');
      aListItem.SubItems[0]:=s;
      aListItem.SubItems[1]:=IntToStr(EPClen);
      aListItem.SubItems[2]:=ANTstr;
      aListItem.SubItems[3]:=RSSI;
      aListItem.SubItems[4]:=strcount;

    end;
    lb_Num.Caption:= IntToStr(CardNum);
    StatusBar1.Panels[0].Text:= FormatDateTime('hh:mm:ss', Now) + '' + 'Read buffer over';
  end;
end;

procedure TfrmRRU9816main.btClearBufferClick(Sender: TObject);
begin
fCmdRet:=ClearBuffer_G2(fComAdr,frmcomportindex);
AddCmdLog('ClearBuffer_G2','Clear Buffer',fCmdRet);
end;

procedure TfrmRRU9816main.btGetAndClBufferClick(Sender: TObject);
begin
  btGetBufferClick(Sender);
  btClearBufferClick(Sender);
end;

procedure TfrmRRU9816main.btGetBufferNumClick(Sender: TObject);
var
  Count:LongInt;
begin
  Count:=0;
  lb_Num.Caption:='0';
  fCmdRet:=GetBufferCnt_G2(fComAdr,Count,frmcomportindex);
  if(fCmdRet=0)then
  begin
     lb_Num.Caption:= IntToStr(Count);
  end;
  AddCmdLog('GetBufferCnt_G2','Get Buffer tag number',fCmdRet);
end;

procedure TfrmRRU9816main.Timer1Timer(Sender: TObject);
var
  CardNum:Integer;
  temps: string;
  s,ss, sEPC: string;
  MaskMem:Byte;
  MaskAdr:array[0..2]of Char;
  MaskLen:Byte;
  MaskData:array[0..800]of Char;
  MaskFlag:Byte;
  Ant,AdrTID,LenTID,TIDFlag:Byte;
  QValue,Session:Byte;
  BufferCount,TagNum:LongInt;
begin
  if fIsInventoryScan then Exit;
  fIsInventoryScan:=True;
  QValue:=4;
  Session:=1;
  FastFlag:=1;
  InAnt:=$80;
  MaskMem:=0;
  MaskFlag:=0;
  if(rb_BEPC.Checked)then
  TIDFlag:=0
  else
  TIDFlag:=1;
  AdrTID:=0;
  LenTID:=6;
  Target:=0;
  Scantime:=3;
  BufferCount:=0;
  TagNum:=0;
  fCmdRet :=InventoryBuffer_G2(fComAdr,QValue,Session,MaskMem,@MaskAdr,MaskLen,@MaskData,MaskFlag,AdrTID,LenTID,TIDFlag,Target,InAnt,Scantime,FastFlag,BufferCount, TagNum,frmcomportindex);
  if(fCmdRet=0)then
  begin
     lb_Num.Caption:=IntToStr(BufferCount);
  end
  else
  begin
    lb_Num.Caption:='0';
  end;
  AddCmdLog('InventoryBuffer_G2','Buffer Inventory',fCmdRet);
  fIsInventoryScan:=False;
end;

procedure TfrmRRU9816main.btClearClick(Sender: TObject);
begin
  lb_Num.Caption:='0';
  ListView1.Items.Clear;
end;

procedure TfrmRRU9816main.ExtWriteClick(Sender: TObject);
var
    Mem,Num:Byte;
    Writedata:array[0..320] of Char;
    WNum:Byte;
    ENum:Byte;
    EPClength:byte;
    i: Integer;
    s,s2: string;
    CardData: array[0..320] of Char;
    WrittenDataNum:LongInt;
    MaskMem:Byte;
    MaskAdr:array[0..2]of Char;
    MaskLen:Byte;
    MaskData:array[0..80]of Char;
    WordPtr:array[0..2]of Char;
begin
    FillChar( MaskData,80,0);
    if(R_EPC.Checked)then MaskMem:=1;
    if(R_TID.Checked)then MaskMem:=2;
    if(R_User.Checked)then MaskMem:=3 ;
    if(CheckBox1.Checked)then
    begin
     ENum:=255;
      if(Edit2.Text='')then Exit;
      if(Edit3.Text='')then Exit;
      if(Edit1.Text='')or(Length(Edit1.Text)mod 2<>0)then Exit;
      getCharStr(Edit2.Text,MaskAdr);
      MaskLen:=StrToInt('$'+trim(edit3.Text));
      getCharStr(Edit1.Text,MaskData);
    end
    else
     ENum:=Length(ComboBox_EPC2.text) div 4;
    if Length(Edit_AccessCode2.Text)<8 then
    begin
     MessageDlg('Access Password Less Than 8 digit!Please input again!', mtInformation, [mbOK], 0);
      Exit;
    end;
    if (Length(Edit_WordPtr.Text)<>4)or(Edit_Len.Text='')then
    begin
     MessageDlg('Start address or length is empty!Please input!', mtInformation, [mbOK], 0);
      Exit;
    end;
    getCharStr(ComboBox_EPC2.text,fOperEPC);
    getCharStr(Edit_AccessCode2.text,fPassword);
    getCharStr(Edit_WordPtr.Text,WordPtr);
    Num:=StrToInt(Edit_Len.Text);
    if  C_Reserve.Checked then
      Mem:=0
    else if  C_EPC.Checked then
      Mem:=1
    else if  C_TID.Checked then
      Mem:=2
    else if  C_User.Checked then
      Mem:=3;
    if ( Edit_WriteData.Text='' )or (Length(Edit_WriteData.Text)mod 4<>0) then
    begin
    MessageDlg('Please input Data in words in hexadecimal form!'+#13+#10+'For example: 1234、12345678', mtInformation, [mbOK], 0);
    Exit;
    end;
    WNum:= Length(Edit_WriteData.text)div 4 ;
    getCharStr(Edit_WriteData.text,Writedata);
    if(CheckBox18.Checked)and(C_EPC.Checked)then
    begin
      getCharStr('0001',WordPtr);
     WNum:= Length(Edit_WriteData.text)div 4 +1;
     getCharStr(edit_pc.Text+Edit_WriteData.text,Writedata);
    end;
    fCmdRet:=ExtWriteData_G2(fComAdr,@fOperEPC,WNum,ENum,Mem,WordPtr,@Writedata,@fPassword,MaskMem,@MaskAdr,MaskLen,@MaskData,ferrorcode,frmComPortindex);
    AddCmdLog('WriteData','Write', fCmdRet,ferrorcode);

end;

procedure TfrmRRU9816main.ExtReadClick(Sender: TObject);
var
    Mem,Num:Byte;
    ENum:byte;
    i: Integer;
    s2: string;
    CardData: array[0..320] of Char;
    MaskMem:Byte;
    MaskAdr:array[0..2]of Char;
    MaskLen:Byte;
    MaskData:array[0..80]of Char;
    WordPtr:array[0..2]of Char;
begin
  FillChar( MaskData,80,0);
  if(R_EPC.Checked)then MaskMem:=1;
  if(R_TID.Checked)then MaskMem:=2;
  if(R_User.Checked)then MaskMem:=3;

  if(CheckBox1.Checked)then
  begin
  ENum:=255;
  if(Edit2.Text='')then Exit;
  if(Edit3.Text='')then Exit;
  if(Edit1.Text='')or(Length(Edit1.Text)mod 2<>0)then Exit;
  getCharStr(Edit2.Text,MaskAdr);
  MaskLen:=StrToInt('$'+trim(edit3.Text));
  getCharStr(Edit1.Text,MaskData);
  END
  else
   ENum:=Length(ComboBox_EPC2.text) div 4;
  if (Length(Edit_WordPtr.Text)<>4)or(Edit_Len.Text='')then
  begin
    MessageDlg('Start address or length is empty!Please input!', mtInformation, [mbOK], 0);
    Exit;
  end;
  getCharStr(ComboBox_EPC2.text,fOperEPC);
  getCharStr(Edit_AccessCode2.text,fPassword);
  getCharStr(Edit_WordPtr.Text,WordPtr);
  Num:=StrToInt(Edit_Len.Text);
  if  C_Reserve.Checked then
    Mem:=0
  else if  C_EPC.Checked then
    Mem:=1
  else if  C_TID.Checked then
    Mem:=2
  else if  C_User.Checked then
    Mem:=3;
  fCmdRet:=ExtReadData_G2(fComAdr,@fOperEPC,ENum,Mem,WordPtr,Num,@fPassword,MaskMem,@MaskAdr,MaskLen,MaskData,@CardData,ferrorcode,frmComPortindex);
  if fCmdRet=0 then
  begin
    for i := 0 to Num*2 - 1 do
    s2 := s2 + IntToHex(ord(CardData[i]), 2);
    Memo_DataShow.Lines.Add(s2);
  end;
  if  fErrorCode<>-1 then
  begin
  StatusBar1.Panels.Items[0].text := FormatDateTime('hh:mm:ss', Now) +
   ' "Read" Response ErrorCode=0x'+ IntToHex(fErrorCode, 2) +
   '(' + RRU9816_GetErrorCodeDesc(fErrorCode) + ')';
    ferrorcode:=-1;
  end
  else
  AddCmdLog('ReadData','Read', fCmdRet);
end;

end.



