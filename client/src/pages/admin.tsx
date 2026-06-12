import { useState } from "react";
import { Link } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { queryClient } from "@/lib/queryClient";
import CalibrationWizard from "@/components/CalibrationWizard";
import { DashboardTab } from "@/components/admin/DashboardTab";
import { CabinetMapTab } from "@/components/admin/CabinetMapTab";
import { BooksTab } from "@/components/admin/BooksTab";
import { UsersTab } from "@/components/admin/UsersTab";
import { OperationsTab } from "@/components/admin/OperationsTab";
import { RfidTestDialog } from "@/components/admin/RfidTestDialog";
import {
  LayoutDashboard, Package, Users, BookOpen, History, Settings,
  ArrowLeft, RefreshCw, Crosshair,
} from "lucide-react";

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [testReader, setTestReader] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-slate-100" data-testid="page-admin">
      <div className="bg-slate-900 text-white p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" className="text-white hover:bg-slate-800" data-testid="button-back-home">
                <ArrowLeft className="w-4 h-4 mr-2" />
                На главную
              </Button>
            </Link>
            <Separator orientation="vertical" className="h-6 bg-slate-600" />
            <h1 className="text-xl font-bold">Панель администратора</h1>
          </div>
          <Button variant="outline" className="border-white text-white" onClick={() => {
            queryClient.invalidateQueries();
          }} data-testid="button-refresh">
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid grid-cols-7 w-full max-w-4xl mb-6">
            <TabsTrigger value="dashboard" className="flex items-center gap-2" data-testid="tab-dashboard">
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="cabinet" className="flex items-center gap-2" data-testid="tab-cabinet">
              <Package className="w-4 h-4" />
              Шкаф
            </TabsTrigger>
            <TabsTrigger value="books" className="flex items-center gap-2" data-testid="tab-books">
              <BookOpen className="w-4 h-4" />
              Книги
            </TabsTrigger>
            <TabsTrigger value="users" className="flex items-center gap-2" data-testid="tab-users">
              <Users className="w-4 h-4" />
              Пользователи
            </TabsTrigger>
            <TabsTrigger value="operations" className="flex items-center gap-2" data-testid="tab-operations">
              <History className="w-4 h-4" />
              Операции
            </TabsTrigger>
            <TabsTrigger value="calibration" className="flex items-center gap-2" data-testid="tab-calibration">
              <Crosshair className="w-4 h-4" />
              Калибровка
            </TabsTrigger>
            <TabsTrigger value="settings" className="flex items-center gap-2" data-testid="tab-settings">
              <Settings className="w-4 h-4" />
              Настройки
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard"><DashboardTab onReaderTest={setTestReader} /></TabsContent>
          <TabsContent value="cabinet"><CabinetMapTab /></TabsContent>
          <TabsContent value="books"><BooksTab /></TabsContent>
          <TabsContent value="users"><UsersTab /></TabsContent>
          <TabsContent value="operations"><OperationsTab /></TabsContent>
          <TabsContent value="calibration">
            <CalibrationWizard />
          </TabsContent>
          <TabsContent value="settings">
            <Card>
              <CardHeader>
                <CardTitle>Настройки системы</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-500">Настройки будут доступны в следующей версии</p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <RfidTestDialog readerId={testReader} onClose={() => setTestReader(null)} />
    </div>
  );
}
