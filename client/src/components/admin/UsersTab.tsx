import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { User } from "@shared/schema";

export function UsersTab() {
  const { data: users = [] } = useQuery<User[]>({ queryKey: ['/api/users'] });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Пользователи</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-96">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2">RFID</th>
                <th className="text-left py-2">Имя</th>
                <th className="text-left py-2">Роль</th>
                <th className="text-left py-2">Email</th>
                <th className="text-left py-2">Статус</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b" data-testid={`row-user-${user.rfid}`}>
                  <td className="py-2 font-mono text-sm">{user.rfid}</td>
                  <td className="py-2">{user.name}</td>
                  <td className="py-2">
                    <Badge variant={
                      user.role === 'admin' ? 'destructive' :
                      user.role === 'librarian' ? 'secondary' : 'default'
                    }>
                      {user.role}
                    </Badge>
                  </td>
                  <td className="py-2 text-slate-500">{user.email || '-'}</td>
                  <td className="py-2">
                    {user.blocked ? (
                      <Badge variant="destructive">Заблокирован</Badge>
                    ) : (
                      <Badge variant="outline">Активен</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
