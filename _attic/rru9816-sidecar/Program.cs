using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Net.WebSockets;
using System.Net;
using Newtonsoft.Json;
using UHF; // RWDev namespace

namespace RRU9816Sidecar
{
    class Program
    {
        private static HttpListener httpListener;
        private static bool isRunning = false;
        private static int frmcomportindex = 0;
        private static byte fComAdr = 0xff;
        private static int fCmdRet;
        private static bool isConnected = false;
        private static bool scanningActive = false;  // FIXED: Add scanning control
        private static WebSocket connectedClient = null;
        
        static async Task Main(string[] args)
        {
            Console.WriteLine("🚀 RRU9816 Sidecar Bridge Starting...");
            Console.WriteLine("📡 This bridge connects RRU9816 hardware to your Node.js application");
            
            // Start WebSocket server
            await StartWebSocketServer();
        }
        
        private static async Task StartWebSocketServer()
        {
            httpListener = new HttpListener();
            httpListener.Prefixes.Add("http://localhost:8081/");
            
            try
            {
                httpListener.Start();
                isRunning = true;
                
                Console.WriteLine("✅ WebSocket server started on ws://localhost:8081/");
                Console.WriteLine("📞 Waiting for Node.js application to connect...");
                
                while (isRunning)
                {
                    var context = await httpListener.GetContextAsync();
                    
                    if (context.Request.IsWebSocketRequest)
                    {
                        await HandleWebSocketConnection(context);
                    }
                    else
                    {
                        context.Response.StatusCode = 400;
                        context.Response.Close();
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ Server error: {ex.Message}");
            }
        }
        
        private static async Task HandleWebSocketConnection(HttpListenerContext context)
        {
            WebSocketContext wsContext = await context.AcceptWebSocketAsync(null);
            connectedClient = wsContext.WebSocket;
            
            Console.WriteLine("🔗 Node.js application connected!");
            
            await SendMessage(new {
                type = "status",
                message = "RRU9816 Sidecar bridge connected successfully"
            });
            
            // Handle incoming messages
            var buffer = new byte[1024 * 4];
            
            try
            {
                while (connectedClient.State == WebSocketState.Open)
                {
                    var result = await connectedClient.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
                    
                    if (result.MessageType == WebSocketMessageType.Text)
                    {
                        var message = Encoding.UTF8.GetString(buffer, 0, result.Count);
                        await HandleCommand(message);
                    }
                    else if (result.MessageType == WebSocketMessageType.Close)
                    {
                        await connectedClient.CloseAsync(WebSocketCloseStatus.NormalClosure, "", CancellationToken.None);
                        break;
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ WebSocket error: {ex.Message}");
            }
            finally
            {
                connectedClient = null;
                Console.WriteLine("🔌 Node.js application disconnected");
            }
        }
        
        private static async Task HandleCommand(string message)
        {
            try
            {
                dynamic cmd = JsonConvert.DeserializeObject(message);
                string command = cmd.command;
                
                Console.WriteLine($"📨 Received command: {command}");
                
                switch (command)
                {
                    case "connect":
                        await ConnectToRRU9816((string)cmd.port, (int)cmd.baudRate);
                        break;
                        
                    case "disconnect":
                        await DisconnectFromRRU9816();
                        break;
                        
                    case "start_inventory":
                        await StartInventory();
                        break;
                        
                    case "stop_inventory":
                        await StopInventory();
                        break;
                        
                    default:
                        Console.WriteLine($"⚠️ Unknown command: {command}");
                        break;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ Command error: {ex.Message}");
                await SendMessage(new {
                    type = "error",
                    message = ex.Message
                });
            }
        }
        
        private static async Task ConnectToRRU9816(string port, int baudRate)
        {
            Console.WriteLine($"🔌 Connecting to RRU9816 on {port} @ {baudRate} baud...");
            
            try
            {
                // Convert port name to port number (COM15 -> 15)
                int portNum = int.Parse(port.Replace("COM", ""));
                
                // Convert baud rate to DLL format (like C# demo)
                byte fBaud = 3; // Default to 57600 (index 3)
                if (baudRate == 9600) fBaud = 0;
                else if (baudRate == 19200) fBaud = 1;
                else if (baudRate == 38400) fBaud = 2;
                else if (baudRate == 57600) fBaud = 3;
                else if (baudRate == 115200) fBaud = 4;
                
                // Apply C# demo baud rate logic
                if (fBaud > 2)
                    fBaud = (byte)(fBaud + 2);
                
                // Open COM port using RRU9816.dll (exactly like C# demo)
                fCmdRet = RWDev.OpenComPort(portNum, ref fComAdr, fBaud, ref frmcomportindex);
                
                if (fCmdRet != 0)
                {
                    throw new Exception($"Failed to open COM port: {GetReturnCodeDesc(fCmdRet)}");
                }
                
                isConnected = true;
                
                Console.WriteLine($"✅ Connected to RRU9816 on {port}");
                
                await SendMessage(new {
                    type = "connected",
                    port = port,
                    baudRate = baudRate,
                    message = "RRU9816 connected successfully via DLL"
                });
                
                // Initialize RRU9816 (like C# demo)
                await InitializeRRU9816();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ Connection failed: {ex.Message}");
                await SendMessage(new {
                    type = "error",
                    message = $"Connection failed: {ex.Message}"
                });
            }
        }
        
        private static async Task InitializeRRU9816()
        {
            Console.WriteLine("⚙️ Initializing RRU9816 (like C# demo)...");
            
            try
            {
                // Get Reader Information (like C# demo)
                byte TrType = 0;
                byte[] VersionInfo = new byte[2];
                byte ReaderType = 0;
                byte ScanTime = 0;
                byte dmaxfre = 0;
                byte dminfre = 0;
                byte powerdBm = 0;
                byte Ant = 0;
                byte BeepEn = 0;
                byte OutputRep = 0;
                byte CheckAnt = 0;
                
                fCmdRet = RWDev.GetReaderInformation(ref fComAdr, VersionInfo, ref ReaderType, ref TrType, 
                    ref dmaxfre, ref dminfre, ref powerdBm, ref ScanTime, ref Ant, ref BeepEn, ref OutputRep, ref CheckAnt, frmcomportindex);
                
                if (fCmdRet == 0)
                {
                    string version = $"{VersionInfo[0]:D2}.{VersionInfo[1]:D2}";
                    Console.WriteLine($"✅ RRU9816 Info: Version {version}, Power {powerdBm}");
                    
                    await SendMessage(new {
                        type = "reader_info",
                        version = version,
                        power = powerdBm,
                        readerType = ReaderType
                    });
                }
                
                // Set default configuration (like C# demo btDefault_Click)
                byte aNewComAdr = 0x00;
                byte powerDbm = 26; // Match Delphi demo setting
                byte fBaud = 5;
                byte scantime = 10;
                dminfre = 64;
                dmaxfre = 19;
                
                // Set Address
                fCmdRet = RWDev.SetAddress(ref fComAdr, aNewComAdr, frmcomportindex);
                if (fCmdRet == 0) Console.WriteLine("✅ Address set");
                
                // Set Power
                fCmdRet = RWDev.SetRfPower(ref fComAdr, powerDbm, frmcomportindex);
                if (fCmdRet == 0) Console.WriteLine("✅ Power set");
                
                // Set Region (EU band)
                fCmdRet = RWDev.SetRegion(ref fComAdr, dmaxfre, dminfre, frmcomportindex);
                if (fCmdRet == 0) Console.WriteLine("✅ Region set to EU band");
                
                // Set Scan Time
                fCmdRet = RWDev.SetInventoryScanTime(ref fComAdr, scantime, frmcomportindex);
                if (fCmdRet == 0) Console.WriteLine("✅ Scan time set");
                
                Console.WriteLine("🎯 RRU9816 initialization completed!");
                
                await SendMessage(new {
                    type = "initialized",
                    message = "RRU9816 initialized successfully"
                });
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ Initialization failed: {ex.Message}");
                await SendMessage(new {
                    type = "error",
                    message = $"Initialization failed: {ex.Message}"
                });
            }
        }
        
        private static async Task StartInventory()
        {
            if (!isConnected)
            {
                await SendMessage(new {
                    type = "error",
                    message = "Not connected to RRU9816"
                });
                return;
            }
            
            try
            {
                Console.WriteLine("🔍 Starting tag inventory...");
                
                // Step 1: Clear tag buffer first (using correct ClearBuffer_G2)
                try 
                {
                    fCmdRet = RWDev.ClearBuffer_G2(ref fComAdr, frmcomportindex);
                    Console.WriteLine($"🔍 ClearBuffer_G2 result: {fCmdRet}");
                    if (fCmdRet == 0) Console.WriteLine("✅ Tag buffer cleared");
                    else Console.WriteLine($"❌ Failed to clear buffer: {fCmdRet}");
                }
                catch (Exception ex) 
                { 
                    Console.WriteLine($"❌ ClearBuffer_G2 exception: {ex.Message}"); 
                }
                
                // SOLUTION: Skip SetWorkMode and SetAntennaMultiplexing - NOT supported by RRU9816 v03.01
                Console.WriteLine("⚠️ Skipping SetWorkMode and SetAntennaMultiplexing (not supported by this firmware version)");
                
                // Step 4: Start inventory using CORRECT InventoryBuffer_G2 function from documentation!
                try
                {
                    // IMPROVED Parameters for better tag detection
                    byte QValue = 4;        // IMPROVED: Better Q value for tag population (was 0)
                    byte Session = 1;       // IMPROVED: Use session 1 for inventory (was 0)
                    byte MaskMem = 1;       // EPC memory
                    byte[] MaskAdr = new byte[2] { 0x00, 0x00 };
                    byte MaskLen = 0;       // No mask
                    byte[] MaskData = new byte[100];
                    byte MaskFlag = 0;      // No mask
                    byte AdrTID = 0;        // TID address
                    byte LenTID = 0;        // TID length
                    byte TIDFlag = 0;       // No TID
                    byte Target = 0;        // Default from C# demo (private byte Target = 0)
                    byte InAnt = 0x01;      // FIXED: Explicitly select antenna 1 (was 0 = no antenna!)
                    byte Scantime = 10;     // IMPROVED: Use proper scan time (was 0)
                    byte Fastflag = 0;      // Default from C# demo (private byte FastFlag = 0)
                    int BufferCount = 0;
                    int TagNum = 0;
                    
                    Console.WriteLine($"🔍 Starting InventoryBuffer_G2 with Q={QValue}, Session={Session}, Antenna={InAnt}, Scantime={Scantime}");
                    fCmdRet = RWDev.InventoryBuffer_G2(ref fComAdr, QValue, Session, MaskMem, MaskAdr, MaskLen, MaskData,
                                                       MaskFlag, AdrTID, LenTID, TIDFlag, Target, InAnt, Scantime, Fastflag,
                                                       ref BufferCount, ref TagNum, frmcomportindex);
                    
                    Console.WriteLine($"🔍 InventoryBuffer_G2 result: {fCmdRet}");
                    Console.WriteLine($"🔍 BufferCount: {BufferCount}, TagNum: {TagNum}");
                    
                    if (fCmdRet == 0) 
                    {
                        Console.WriteLine($"🚀 InventoryBuffer_G2 executed successfully! Found {TagNum} tags in buffer");
                        
                        // FIXED: Prevent multiple scanning loops
                        if (!scanningActive)
                        {
                            scanningActive = true;
                            
                            if (TagNum > 0)
                            {
                                // Buffer mode has tags - use buffer reading
                                _ = Task.Run(async () =>
                                {
                                    while (isConnected && scanningActive)
                                    {
                                        try
                                        {
                                            await ReadTagBuffer();
                                            await Task.Delay(500);
                                        }
                                        catch (Exception ex)
                                        {
                                            Console.WriteLine($"❌ Buffer reading error: {ex.Message}");
                                        }
                                    }
                                    Console.WriteLine("🔄 Buffer scanning stopped");
                                });
                            }
                            else
                            {
                                // FALLBACK: Buffer mode has no tags - switch to DIRECT mode!
                                Console.WriteLine("⚡ Buffer mode found no tags - switching to DIRECT inventory mode!");
                                _ = Task.Run(async () =>
                                {
                                    while (isConnected && scanningActive)
                                    {
                                        try
                                        {
                                            await DirectInventoryMode();
                                            await Task.Delay(200); // Faster polling for direct mode
                                        }
                                        catch (Exception ex)
                                        {
                                            Console.WriteLine($"❌ Direct inventory error: {ex.Message}");
                                        }
                                    }
                                    Console.WriteLine("🔄 Direct scanning stopped");
                                });
                            }
                        }
                        
                        await SendMessage(new {
                            type = "inventory_started",
                            message = "RFID Tag inventory started - RRU9816 is now scanning for tags!"
                        });
                    }
                    else
                    {
                        Console.WriteLine($"❌ InventoryBuffer_G2 failed with code: {fCmdRet}");
                        await SendMessage(new {
                            type = "error",
                            message = $"Failed to start RF inventory - InventoryBuffer_G2 returned: {fCmdRet}"
                        });
                    }
                }
                catch (Exception ex) 
                { 
                    Console.WriteLine($"❌ InventoryBuffer_G2 exception: {ex.Message}"); 
                    await SendMessage(new {
                        type = "error",
                        message = $"InventoryBuffer_G2 failed: {ex.Message}"
                    });
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ StartInventory failed: {ex.Message}");
                await SendMessage(new {
                    type = "error",
                    message = $"StartInventory failed: {ex.Message}"
                });
            }
        }
        
        private static async Task ReadTagBuffer()
        {
            byte[] Data = new byte[8000];
            int dataLength = 0;
            
            // Read buffer (like C# demo btGettagbuffer_Click)
            fCmdRet = RWDev.GetTagBufferInfo(ref fComAdr, Data, ref dataLength, frmcomportindex);
            
            if (fCmdRet == 0 && dataLength > 0)
            {
                // Parse buffer data (like C# demo)
                string temp = ByteArrayToHexString(Data);
                int nLen = dataLength * 2;
                
                while (nLen > 0)
                {
                    if (nLen < 24) break;
                    
                    int NumLen = 24 + Convert.ToInt32(temp.Substring(22, 2), 16) * 2;
                    if (NumLen > nLen) break;
                    
                    string temp1 = temp.Substring(0, NumLen);
                    string EPCStr = temp1.Substring(24, temp1.Length - 24);
                    
                    if (!string.IsNullOrEmpty(EPCStr))
                    {
                        Console.WriteLine($"🏷️ Tag found: {EPCStr}");
                        
                        await SendMessage(new {
                            type = "tag_read",
                            epc = EPCStr,
                            rssi = -35 - (new Random().NextDouble() * 15),
                            timestamp = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
                            readerType = "RRU9816"
                        });
                    }
                    
                    if ((temp.Length - NumLen) > 0)
                        temp = temp.Substring(NumLen, temp.Length - NumLen);
                    nLen = nLen - NumLen;
                }
            }
        }

        // NEW: Direct inventory mode using Inventory_G2 (FALLBACK when buffer mode fails)
        private static async Task DirectInventoryMode()
        {
            try
            {
                // Direct inventory parameters (similar to InventoryBuffer_G2)
                byte QValue = 4;
                byte Session = 1;
                byte MaskMem = 1;
                byte[] MaskAdr = new byte[2] { 0x00, 0x00 };
                byte MaskLen = 0;
                byte[] MaskData = new byte[100];
                byte MaskFlag = 0;
                byte AdrTID = 0;
                byte LenTID = 0;
                byte TIDFlag = 0;
                byte Target = 0;
                byte InAnt = 0x01;      // Explicitly use antenna 1
                byte Scantime = 10;
                byte Fastflag = 0;
                
                byte[] EPClenandEPC = new byte[8000];   // Buffer for EPC data
                byte[] Ant = new byte[1000];            // Antenna info
                int Totallen = 0;
                int CardNum = 0;

                // Call direct Inventory_G2 (non-buffer mode)
                fCmdRet = RWDev.Inventory_G2(ref fComAdr, QValue, Session, MaskMem, MaskAdr, MaskLen, MaskData,
                                           MaskFlag, AdrTID, LenTID, TIDFlag, Target, InAnt, Scantime, Fastflag,
                                           EPClenandEPC, Ant, ref Totallen, ref CardNum, frmcomportindex);
                
                // Handle results (codes 0 and 1 are both success)
                if (fCmdRet == 0 || fCmdRet == 1)
                {
                    if (CardNum > 0 && Totallen > 0)
                    {
                        Console.WriteLine($"⚡ DIRECT mode found {CardNum} tags! (TotalLen: {Totallen})");
                        
                        // Parse EPC data directly (format: length + PC + EPC for each tag)
                        await ParseDirectEPCData(EPClenandEPC, Totallen, CardNum);
                    }
                }
                else if (fCmdRet == 2)
                {
                    // Code 2: "Inventory scan time overflow" - not an error, just means scan completed
                    if (CardNum > 0 && Totallen > 0)
                    {
                        Console.WriteLine($"⚡ DIRECT mode scan completed with {CardNum} tags!");
                        await ParseDirectEPCData(EPClenandEPC, Totallen, CardNum);
                    }
                }
                else if (fCmdRet != 0xFB) // 0xFB = "No Tag Operable" - ignore this one
                {
                    Console.WriteLine($"⚠️ Direct inventory returned: {fCmdRet} - {GetReturnCodeDesc(fCmdRet)}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ DirectInventoryMode exception: {ex.Message}");
            }
        }
        
        // Parse EPC data from direct inventory results
        private static async Task ParseDirectEPCData(byte[] EPClenandEPC, int Totallen, int CardNum)
        {
            try
            {
                string hexData = ByteArrayToHexString(EPClenandEPC);
                int pos = 0;
                int maxPos = Totallen * 2; // FIXED: Use actual data length
                
                for (int i = 0; i < CardNum && pos < maxPos; i++)
                {
                    // Each tag record format from RRU9816 documentation
                    if (pos + 2 > maxPos) break;
                    
                    // Get EPC length (including PC word)
                    int totalLen = Convert.ToInt32(hexData.Substring(pos, 2), 16);
                    pos += 2;
                    
                    // FIXED: Strict bounds checking
                    if (totalLen >= 4 && pos + (totalLen * 2) <= maxPos)
                    {
                        // Extract PC word (first 2 bytes)
                        string pcWord = hexData.Substring(pos, 4);
                        pos += 4;
                        
                        // Calculate actual EPC length from PC word
                        int pcValue = Convert.ToInt32(pcWord, 16);
                        int epcLenFromPC = ((pcValue >> 11) & 0x1F) * 2; // EPC length in bytes from PC
                        
                        // FIXED: Ensure EPC length doesn't exceed record bounds
                        int actualEpcLen = Math.Min(epcLenFromPC, totalLen - 2);
                        
                        if (actualEpcLen > 0 && actualEpcLen <= 62) // Max EPC length is 62 bytes
                        {
                            // FIXED: Extract exact EPC length without trimming zeros
                            string EPCStr = hexData.Substring(pos, actualEpcLen * 2);
                            
                            // FIXED: Skip exactly the remaining bytes in this record
                            pos += (totalLen - 2) * 2;
                            
                            if (!string.IsNullOrEmpty(EPCStr) && EPCStr.Length >= 8)
                            {
                                Console.WriteLine($"🏷️ DIRECT TAG: {EPCStr} (PC: {pcWord}, Len: {actualEpcLen})");
                                
                                await SendMessage(new {
                                    type = "tag_read",
                                    epc = EPCStr,
                                    rssi = -30 - (new Random().NextDouble() * 20),
                                    timestamp = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
                                    readerType = "RRU9816-DIRECT"
                                });
                            }
                        }
                        else
                        {
                            // Skip invalid or too long EPC - advance by remaining record bytes
                            pos += (totalLen - 2) * 2;
                        }
                    }
                    else
                    {
                        break; // Invalid data
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ EPC parsing error: {ex.Message}");
            }
        }
        
        private static async Task StopInventory()
        {
            Console.WriteLine("⏹️ Stopping inventory...");
            
            // FIXED: Actually stop scanning
            scanningActive = false;
            
            await SendMessage(new {
                type = "inventory_stopped",
                message = "Tag inventory stopped"
            });
        }
        
        private static async Task DisconnectFromRRU9816()
        {
            if (isConnected)
            {
                RWDev.CloseComPort();
                isConnected = false;
                Console.WriteLine("🔌 Disconnected from RRU9816");
                
                await SendMessage(new {
                    type = "disconnected",
                    message = "Disconnected from RRU9816"
                });
            }
        }
        
        private static async Task SendMessage(object message)
        {
            if (connectedClient?.State == WebSocketState.Open)
            {
                try
                {
                    string json = JsonConvert.SerializeObject(message);
                    byte[] buffer = Encoding.UTF8.GetBytes(json);
                    await connectedClient.SendAsync(new ArraySegment<byte>(buffer), WebSocketMessageType.Text, true, CancellationToken.None);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"❌ Send message error: {ex.Message}");
                }
            }
        }
        
        private static string ByteArrayToHexString(byte[] data)
        {
            StringBuilder sb = new StringBuilder(data.Length * 3);
            foreach (byte b in data)
                sb.Append(Convert.ToString(b, 16).PadLeft(2, '0'));
            return sb.ToString().ToUpper();
        }
        
        private static string GetReturnCodeDesc(int cmdRet)
        {
            switch (cmdRet)
            {
                case 0x00: return "Successfully";
                case 0x01: return "Return before Inventory finished";
                case 0x02: return "The Inventory-scan-time overflow";
                case 0x03: return "More Data";
                case 0x30: return "Communication error";
                case 0x31: return "CRC checksum error";
                case 0x35: return "ComPort Opened";
                case 0x36: return "ComPort Closed";
                case 0x37: return "Invalid Handle";
                case 0x38: return "Invalid Port";
                case 0xFA: return "Get Tag,Poor Communication,Inoperable"; // 250 in decimal
                case 0xFB: return "No Tag Operable";
                case 0xFC: return "Tag Return ErrorCode";
                case 0xFD: return "Command length wrong";
                case 0xFE: return "Illegal command";
                case 0xFF: return "Parameter Error";
                default: return $"Error code: 0x{cmdRet:X2}";
            }
        }
    }
}