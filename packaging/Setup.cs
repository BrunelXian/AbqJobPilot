using System;using System.IO;using System.IO.Compression;using System.Linq;using System.Collections.Generic;using System.Diagnostics;using System.Reflection;using System.Security.Cryptography;using System.Text;using System.Threading;using System.Windows.Forms;using System.Web.Script.Serialization;using Microsoft.Win32;
class Setup {
 const string Product="AbqJobPilot-050-Candidate024";
 static JavaScriptSerializer J=new JavaScriptSerializer(){MaxJsonLength=20000000};
 static string Marker=".abqjobpilot-install.json";
 static string Quote(string s){return "\""+s.Replace("\"","")+"\"";}
 static string Hash(string p){using(var s=File.OpenRead(p))using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(s)).Replace("-","").ToLowerInvariant();}
 static string Full(string p){return Path.GetFullPath(p).TrimEnd(Path.DirectorySeparatorChar);}
 static void Plain(string path){string p=Full(path);for(string x=p;!String.IsNullOrEmpty(x);x=Path.GetDirectoryName(x)){if((Directory.Exists(x)||File.Exists(x))&&(File.GetAttributes(x)&FileAttributes.ReparsePoint)!=0)throw new Exception("Reparse paths are not supported: "+x);}}
 static void SafeRoot(string root){
  root=Full(root);Plain(root);if(root.Length<8||root.Equals(Full(Path.GetPathRoot(root)),StringComparison.OrdinalIgnoreCase))throw new Exception("Invalid installation root");
  var protectedNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "abqjobpilot", "abqjobpilot_dev", "abqjobpilot_archived", ".abqjobpilot", ".git" };
  for (var dir = new DirectoryInfo(root); dir != null; dir = dir.Parent) {
   if (protectedNames.Contains(dir.Name)) throw new Exception("Protected source/data path cannot be an install target");
  }
 }
 static string Child(string root,string rel){if(String.IsNullOrEmpty(rel)||Path.IsPathRooted(rel)||rel.Contains(":"))throw new Exception("Invalid package path");string p=Path.GetFullPath(Path.Combine(root,rel.Replace('/',Path.DirectorySeparatorChar)));if(!p.StartsWith(Full(root)+"\\",StringComparison.OrdinalIgnoreCase))throw new Exception("Package path escapes root");Plain(p);return p;}
 static Dictionary<string,object> Load(string p){return J.Deserialize<Dictionary<string,object>>(File.ReadAllText(p));}
 static string Reg(string id){return @"Software\Microsoft\Windows\CurrentVersion\Uninstall\"+id;}
 static string StartLink(string id){
  string folder=Environment.GetFolderPath(Environment.SpecialFolder.Programs);
  if(String.IsNullOrEmpty(folder)){
   string roaming=Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
   if(String.IsNullOrEmpty(roaming)||!Path.IsPathRooted(roaming))throw new InvalidOperationException("USER_START_MENU_UNAVAILABLE: Current-user application data directory is unavailable");
   folder=Path.Combine(roaming,"Microsoft","Windows","Start Menu","Programs");
  }
  Plain(folder);return Path.Combine(folder,id+".lnk");
 }
 static void Shortcut(string root,string id){
  string link=StartLink(id);Directory.CreateDirectory(Path.GetDirectoryName(link));
  Type t=Type.GetTypeFromProgID("WScript.Shell");dynamic shell=Activator.CreateInstance(t);dynamic s=shell.CreateShortcut(link);s.TargetPath=Path.Combine(root,"AbqJobPilot","AbqJobPilot.exe");s.WorkingDirectory=root;s.Description="AbqJobPilot Windows Release Candidate";s.Save();
 }
 static void Register(string root,string id){using(var k=Registry.CurrentUser.CreateSubKey(Reg(id))){k.SetValue("DisplayName","AbqJobPilot 0.5.0 candidate024"+(id==Product?"":" (isolated test)"));k.SetValue("DisplayVersion","0.5.0");k.SetValue("InstallLocation",root);k.SetValue("UninstallString",Quote(Path.Combine(root,"Uninstall.exe")));k.SetValue("QuietUninstallString",Quote(Path.Combine(root,"Uninstall.exe"))+" --silent");k.SetValue("NoModify",1);k.SetValue("NoRepair",1);}}
 static string Get(string[] a,string key,string fallback=null){int n=Array.IndexOf(a,key);return n>=0&&n+1<a.Length?a[n+1]:fallback;}
 static void EnsureIdle(string root){
  foreach(var p in Process.GetProcesses()){string exe;try{exe=p.MainModule.FileName;}catch{continue;}if(p.Id!=Process.GetCurrentProcess().Id&&exe.StartsWith(root+"\\",StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("Close the installed application/service before update or uninstall (PID "+p.Id+")");}
 }
 static Dictionary<string,object> ValidMarker(string root){
  SafeRoot(root);
  string path=Path.Combine(root,Marker);
  if(!File.Exists(path))throw new InvalidOperationException("INSTALL_METADATA_MISSING: Installation metadata is missing from "+root+". Preserve this directory and install into a new empty folder. Do not create metadata manually.");
  try {
   var m=Load(path);
   if((string)m["product"]!=Product||!Full((string)m["root"]).Equals(Full(root),StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("Installation identity mismatch");
   return m;
  }catch(Exception e){throw new InvalidOperationException("INSTALL_METADATA_INVALID: Cannot validate the installation at "+root+". "+e.Message,e);}
 }
 static bool LooksInstalled(string root){
  return File.Exists(Path.Combine(root,"AbqJobPilot","AbqJobPilot.exe"))||File.Exists(Path.Combine(root,"Uninstall.exe"))||
         File.Exists(Path.Combine(root,"FILES.json"))||File.Exists(Path.Combine(root,"runtime","python.exe"));
 }
 static bool RegisteredAt(string root,string id){
  using(var key=Registry.CurrentUser.OpenSubKey(Reg(id))){
   return key!=null&&Full((string)key.GetValue("InstallLocation","")).Equals(root,StringComparison.OrdinalIgnoreCase);
  }
 }
 static string ResolveTarget(string selected,string id){
  if(String.IsNullOrWhiteSpace(selected)||!Path.IsPathRooted(selected))throw new InvalidOperationException("INSTALL_TARGET_INVALID: Select an absolute installation directory.");
  string root=Full(selected);SafeRoot(root);
  if(File.Exists(root))throw new InvalidOperationException("INSTALL_TARGET_INVALID: Select a directory.");
  if(File.Exists(Path.Combine(root,Marker))){ValidMarker(root);return root;}
  if(RegisteredAt(root,id)||LooksInstalled(root)){
   throw new InvalidOperationException("INSTALL_METADATA_MISSING: An existing installation at "+root+" has no valid metadata. Preserve it and choose a new empty folder. Do not create metadata manually.");
  }
  if(!Directory.Exists(root)||!Directory.EnumerateFileSystemEntries(root).Any())return root;
  // An ordinary, populated directory is a parent, never an existing installation.
  string child=Path.Combine(root,"AbqJobPilot-050-Candidate024");SafeRoot(child);
  if(File.Exists(Path.Combine(child,Marker))){ValidMarker(child);return child;}
  if(RegisteredAt(child,id)||LooksInstalled(child))throw new InvalidOperationException("INSTALL_METADATA_MISSING: Preserve the existing installation at "+child+" and choose a new empty folder.");
  if(File.Exists(child)||(Directory.Exists(child)&&Directory.EnumerateFileSystemEntries(child).Any()))throw new InvalidOperationException("INSTALL_TARGET_OCCUPIED: "+child+" contains unrecognized files. Choose a new empty folder.");
  return child;
 }
 static void Install(string root,string id){
  root=ResolveTarget(root,id);SafeRoot(root);string parent=Path.GetDirectoryName(root);Directory.CreateDirectory(parent);
  using(var existing=Registry.CurrentUser.OpenSubKey(Reg(id))){if(existing!=null){string installed=(string)existing.GetValue("InstallLocation","");if(!Full(installed).Equals(root,StringComparison.OrdinalIgnoreCase))throw new Exception("This RC is already registered at "+installed+". Update that directory or uninstall it first.");}}
  string stage=Path.Combine(parent,".abq-stage-"+Guid.NewGuid().ToString("N")),backup=null;Dictionary<string,object> previous=null;
  if(Directory.Exists(root)){
   if(File.Exists(Path.Combine(root,Marker))){previous=ValidMarker(root);if((string)previous["registryId"]!=id)throw new Exception("Existing install belongs to a different channel");EnsureIdle(root);}
   else if(Directory.EnumerateFileSystemEntries(root).Any())throw new InvalidOperationException("INSTALL_TARGET_CHANGED: Target gained files; nothing overwritten.");
  }
  Directory.CreateDirectory(stage);bool published=false;string token=Guid.NewGuid().ToString("N");
  try {
   using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")){
    if(stream==null)throw new Exception("This executable has no installer payload");
    using(var zip=new ZipArchive(stream,ZipArchiveMode.Read))foreach(var e in zip.Entries){if(e.FullName.EndsWith("/"))continue;string dest=Child(stage,e.FullName);Directory.CreateDirectory(Path.GetDirectoryName(dest));using(var input=e.Open())using(var output=new FileStream(dest,FileMode.CreateNew))input.CopyTo(output);}
   }
   var files=J.Deserialize<List<Dictionary<string,string>>>(File.ReadAllText(Path.Combine(stage,"FILES.json")));
   foreach(var f in files)if(Hash(Child(stage,f["path"]))!=f["sha256"])throw new Exception("Package checksum mismatch: "+f["path"]);
   files.Add(new Dictionary<string,string>{{"path","FILES.json"},{"sha256",Hash(Path.Combine(stage,"FILES.json"))}});
   var m=new Dictionary<string,object>{{"product",Product},{"root",root},{"registryId",id},{"token",token},{"files",files}};
   File.WriteAllText(Path.Combine(stage,Marker),J.Serialize(m),new UTF8Encoding(false));
   if(previous!=null){backup=root+".previous-"+Guid.NewGuid().ToString("N");Directory.Move(root,backup);}
   // Delete only an empty target at publication; concurrent content makes this fail safely.
   if(previous==null&&Directory.Exists(root))Directory.Delete(root,false);
   Directory.Move(stage,root);published=true;Register(root,id);Shortcut(root,id);
   Console.WriteLine("INSTALLED "+root);if(backup!=null)Console.WriteLine("PREVIOUS INSTALL RETAINED "+backup);
  }catch{
   // Never delete an unsuccessful extraction or overwrite existing files.
   if(published){string failed=root+".failed-"+Guid.NewGuid().ToString("N");Directory.Move(root,failed);}
   if(backup!=null&&!Directory.Exists(root)){Directory.Move(backup,root);Register(root,id);Shortcut(root,id);}
   else if(previous==null){using(var k=Registry.CurrentUser.OpenSubKey(Reg(id))){if(k!=null&&Full((string)k.GetValue("InstallLocation","")).Equals(root,StringComparison.OrdinalIgnoreCase))Registry.CurrentUser.DeleteSubKeyTree(Reg(id));}string link=StartLink(id);if(File.Exists(link)){Type t=Type.GetTypeFromProgID("WScript.Shell");dynamic sh=Activator.CreateInstance(t);dynamic l=sh.CreateShortcut(link);if(Full((string)l.TargetPath).Equals(Full(Path.Combine(root,"AbqJobPilot","AbqJobPilot.exe")),StringComparison.OrdinalIgnoreCase))File.Delete(link);}}
   throw;
  }
 }
 static void Remove(string root,string token,string report){
  root=Full(root);var m=ValidMarker(root);if((string)m["token"]!=token)throw new Exception("Uninstall token mismatch");EnsureIdle(root);
  var files=J.ConvertToType<List<Dictionary<string,string>>>(m["files"]);var preserved=new List<string>();
  foreach(var f in files){string p=Child(root,f["path"]);if(!File.Exists(p))continue;if(Hash(p)!=f["sha256"]){preserved.Add(f["path"]);continue;}File.Delete(p);}
  File.Delete(Path.Combine(root,Marker));
  string id=(string)m["registryId"];using(var key=Registry.CurrentUser.OpenSubKey(Reg(id))){if(key!=null&&Full((string)key.GetValue("InstallLocation","")).Equals(root,StringComparison.OrdinalIgnoreCase)){Registry.CurrentUser.DeleteSubKeyTree(Reg(id));}}
  string link=StartLink(id);if(File.Exists(link)){Type t=Type.GetTypeFromProgID("WScript.Shell");dynamic sh=Activator.CreateInstance(t);dynamic l=sh.CreateShortcut(link);if(Full((string)l.TargetPath).Equals(Full(Path.Combine(root,"AbqJobPilot","AbqJobPilot.exe")),StringComparison.OrdinalIgnoreCase))File.Delete(link);}
  // Empty directories only; unknown/changed user files are never removed.
  var dirs=new HashSet<string>(StringComparer.OrdinalIgnoreCase);foreach(var f in files){string parent=Path.GetDirectoryName(Child(root,f["path"]));while(parent!=null&&parent.StartsWith(root+"\\",StringComparison.OrdinalIgnoreCase)){dirs.Add(parent);parent=Path.GetDirectoryName(parent);}}
  foreach(var dir in dirs.OrderByDescending(x=>x.Length)){if(!Directory.Exists(dir))continue;Plain(dir);if(!Directory.EnumerateFileSystemEntries(dir).Any())Directory.Delete(dir);}
  if(!Directory.EnumerateFileSystemEntries(root).Any())Directory.Delete(root);
  var r=new Dictionary<string,object>{{"status","UNINSTALLED"},{"root",root},{"preservedChangedFiles",preserved},{"projectDataDeleted",false}};
  if(report!=null)File.WriteAllText(report,J.Serialize(r),new UTF8Encoding(false));
 }
 [STAThread]static int Main(string[] args){bool silent=args.Contains("--silent");try{
  string own=Assembly.GetExecutingAssembly().Location;
  if(args.Contains("--remove")){
   string root=Get(args,"--remove"),token=Get(args,"--token");int pid=Int32.Parse(Get(args,"--wait-pid","0"));if(pid!=0)try{Process.GetProcessById(pid).WaitForExit(30000);}catch(ArgumentException){}
   Remove(root,token,Get(args,"--report"));return 0;
  }
  if(Path.GetFileName(own).Equals("Uninstall.exe",StringComparison.OrdinalIgnoreCase)){
   string root=Full(Path.GetDirectoryName(own));var m=ValidMarker(root);if(!silent&&MessageBox.Show("Uninstall AbqJobPilot RC? Projects and user settings are preserved.","AbqJobPilot RC",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes)return 0;
   EnsureIdle(root);string helper=Path.Combine(Path.GetTempPath(),"AbqJobPilot-remove-"+Guid.NewGuid().ToString("N")+".exe");File.Copy(own,helper,false);
   string report=Get(args,"--report");string command="--silent --remove "+Quote(root)+" --token "+Quote((string)m["token"])+" --wait-pid "+Process.GetCurrentProcess().Id+(report==null?"":" --report "+Quote(report));
   Process.Start(new ProcessStartInfo(helper,command){UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=Path.GetTempPath()});return 0;
  }
  string suffix=Get(args,"--test-id","");if(suffix.Any(c=>!Char.IsLetterOrDigit(c)&&c!='-'))throw new Exception("Invalid test id");string id=Product+(suffix==""?"":"-Test-"+suffix);
  string target=Get(args,"--target",Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Programs","AbqJobPilot-050-Candidate024"));
  if(!silent){
   Application.EnableVisualStyles();
   using(var f=new Form()){
    f.Text="Install AbqJobPilot 0.5.0 candidate024";f.Width=740;f.Height=360;f.StartPosition=FormStartPosition.CenterScreen;
    var label=new Label(){Left=18,Top=18,Width=690,Height=48,Text="Install for the current Windows user. Python and Tk are included.\nSelect a new/empty install folder, or a parent directory for a new candidate024 subfolder."};
    var box=new TextBox(){Left=18,Top=78,Width=690,Text=target};
    var browse=new Button(){Left=18,Top=118,Text="Browse...",Width=95};
    var destination=new Label(){Left=18,Top=158,Width=690,Height=90};
    var install=new Button(){Left=510,Top=270,Text="Install",Width=95};
    var cancel=new Button(){Left=615,Top=270,Text="Cancel",Width=95,DialogResult=DialogResult.Cancel};
    Action refresh=()=>{
     try{destination.Text="Files will be installed to:\n"+ResolveTarget(box.Text,id);install.Enabled=true;}
     catch(Exception e){destination.Text=e.Message;install.Enabled=false;}
    };
    box.TextChanged+=(s,e)=>refresh();
    browse.Click+=(s,e)=>{using(var d=new FolderBrowserDialog()){if(d.ShowDialog()==DialogResult.OK)box.Text=d.SelectedPath;}};
    install.Click+=(s,e)=>{
     try{target=ResolveTarget(box.Text,id);f.DialogResult=DialogResult.OK;}
     catch(Exception ex){destination.Text=ex.Message;install.Enabled=false;}
    };
    f.Controls.AddRange(new Control[]{label,box,browse,destination,install,cancel});
    f.AcceptButton=install;f.CancelButton=cancel;refresh();
    if(f.ShowDialog()!=DialogResult.OK)return 0;
   }
  }
  Install(target,id);if(!silent)MessageBox.Show("Installed. Use Start Menu: "+id+".\nNo Solver or Project was started.","AbqJobPilot RC");return 0;
 }catch(Exception e){Console.Error.WriteLine(e.Message);if(!silent)MessageBox.Show(e.Message,"AbqJobPilot RC",MessageBoxButtons.OK,MessageBoxIcon.Error);return 1;}}
}
