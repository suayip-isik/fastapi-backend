# Codex CLI Rule — RBAC ve Permission-Driven UI Mimari Standardı

Bu doküman, Codex CLI veya benzeri bir AI coding agent'ın projede **RBAC (Role-Based Access Control)** ve **permission-driven UI** geliştirmesi yaparken uyması gereken zorunlu kuralları tanımlar.

Bu rule'ın amacı:

- permission modelini standardize etmek
- frontend ve backend arasında tek dil oluşturmak
- `view yok ama update var` gibi karmaşık senaryoları doğru ele almak
- güvenlik, sürdürülebilirlik ve ölçeklenebilirliği korumak

---

## 1. Temel kural

Agent, yetkilendirme tasarlarken veya geliştirirken **role tabanlı kaba kontrol** yerine **permission tabanlı ince kontrol** uygulamalıdır.

### Zorunlu ilke

- **Role**, kullanıcı gruplama katmanıdır.
- **Permission**, kullanıcının gerçekte ne yapabildiğini tanımlar.
- UI görünürlüğü, sayfa erişimi ve iş aksiyonları aynı kavram olarak ele alınmamalıdır.
- Frontend güvenlik otoritesi değildir.
- Nihai yetki kontrolü her zaman backend tarafında uygulanmalıdır.

---

## 2. Permission isimlendirme standardı

Agent, yeni permission tanımlarken aşağıdaki formatı kullanmalıdır:

```txt
resource.action.scope
```

Her permission üç parçalı olmak zorunda değildir, ancak isimlendirme mantığı bu standardı takip etmelidir.

### Doğru örnekler

```txt
users.list
users.read.basic
users.read.detail
users.read.sensitive
users.create
users.update.profile
users.update.status
users.update.role
users.delete
users.reset_password
orders.approve
payments.refund
```

### Yanlış örnekler

```txt
userAccess
canEditUser
manageUsers
updateUser
readAll
```

### Zorunlu kurallar

- Permission isimleri küçük harf ve nokta ayrımlı olmalıdır.
- Permission isimleri iş anlamını açık taşımalıdır.
- Tek bir permission birden fazla belirsiz aksiyonu temsil etmemelidir.
- `manage`, `full`, `allAccess` gibi muğlak isimlerden kaçınılmalıdır.

---

## 3. `read` permission'ları parçalanmalıdır

Agent, tek bir genel `read` permission'ı kullanmamalıdır; gerektiğinde okuma yetkisini katmanlandırmalıdır.

### Önerilen katmanlar

```txt
users.read.basic
users.read.detail
users.read.sensitive
```

### Uygulama anlamı

#### `users.read.basic`

Gösterilebilecek örnek alanlar:

- ad
- soyad
- e-posta
- durum
- oluşturulma tarihi

#### `users.read.detail`

Ek olarak gösterilebilecek alanlar:

- son giriş tarihi
- bağlı ekip
- notlar
- audit bilgileri

#### `users.read.sensitive`

Ek olarak gösterilebilecek alanlar:

- maaş
- kimlik bilgileri
- hassas finansal veriler
- özel iletişim bilgileri

### Zorunlu kural

Hassas alanlar hiçbir zaman `basic` veya `detail` ile aynı permission altında toplanmamalıdır.

---

## 4. `update` permission'ları parçalanmalıdır

Agent, tek bir genel `update` permission'ı üretmemelidir; güncelleme yetkilerini alan veya işlev bazlı bölmelidir.

### Doğru yaklaşım

```txt
users.update.profile
users.update.status
users.update.role
users.update.permissions
```

### Gerekçe

Aşağıdaki işlemler teknik olarak update olsa da iş açısından farklıdır:

- profil güncelleme
- durum değiştirme
- rol değiştirme
- yetki değiştirme
- şifre sıfırlama

### Zorunlu kural

Aşağıdaki aksiyonlar `update` altında ezilmemelidir; ayrı business action olarak modellenmelidir:

```txt
users.reset_password
orders.approve
orders.reject
payments.refund
tickets.assign
invoices.cancel
```

---

## 5. Route izinleri ile action izinleri ayrılmalıdır

Agent, sayfa erişimi ile sayfa içindeki aksiyonları aynı permission üzerinden modellememelidir.

### Route permission örnekleri

```txt
/admin/users      -> users.list
/admin/users/[id] -> users.read.basic
/admin/roles      -> roles.list
/admin/settings   -> settings.read
```

### Action permission örnekleri

```txt
Yeni kullanıcı ekle   -> users.create
Detay drawer aç       -> users.read.basic
Hassas bilgi sekmesi  -> users.read.sensitive
Profil düzenle        -> users.update.profile
Durum değiştir        -> users.update.status
Rol ata               -> users.update.role
Sil                   -> users.delete
```

### Zorunlu kural

Bir kullanıcı bir route'a erişebiliyor diye o sayfadaki tüm aksiyonlara da erişebiliyor varsayılmamalıdır.

---

## 6. `view yok ama update var` senaryosu nasıl ele alınmalıdır

Agent, `view yok ama update var` senaryosunda full detay ekranı göstermemelidir.

### Uygulanacak karar ağacı

#### Durum 1: Update işlemi minimum read gerektiriyorsa

Agent aşağıdaki yaklaşımı uygulamalıdır:

- update yapılacak alan için gerekli minimum bağlamı belirle
- gerekiyorsa `read.basic` benzeri minimum read izni tanımla
- tam detay ekranı yerine sınırlı görünüm kullan

#### Durum 2: Kullanıcı sadece belirli bir alanı değiştirebiliyorsa

Agent aşağıdaki yapıyı kurmalıdır:

- liste ekranı gösterilebilir
- detay sayfası kapalı tutulabilir
- tablo satırında aksiyon butonu gösterilebilir
- aksiyon bir modal, drawer veya inline editor açmalıdır
- bu UI yalnızca düzenlenebilir alanları içermelidir

Örnek:

- kullanıcıda `users.list` vardır
- kullanıcıda `users.update.status` vardır
- kullanıcıda `users.read.detail` yoktur

Bu durumda doğru davranış:

- kullanıcı listeyi görür
- detay sayfasına gidemez
- satırdaki `Durum Güncelle` butonunu görür
- açılan modal sadece `status` alanını gösterir

#### Durum 3: İşlem aslında business action ise

Agent bunu `update` olarak değil, açık isimli business action permission olarak modellemelidir.

Örnek:

```txt
users.activate
orders.approve
orders.reject
tickets.assign
```

### Zorunlu kural

`view yok ama update var` durumu oluştuğunda agent, varsayılan olarak full detail page render etmemelidir.

---

## 7. UI kontrolü üç katmanda yapılmalıdır

Agent, permission kontrolünü yalnızca buton gizleme seviyesinde bırakmamalıdır. UI tarafında minimum üç katman uygulanmalıdır.

### 7.1 Navigation seviyesi

Kural:

- Kullanıcının modülü menüde görüp göremeyeceği permission ile belirlenmelidir.

Örnek:

```ts
const canSeeUsersMenu = hasPermission("users.list");
```

### 7.2 Route seviyesi

Kural:

- Kullanıcı URL'yi manuel yazsa bile yetkisi yoksa route render edilmemelidir.
- Yetkisiz durumda `403` veya uygun erişim yok ekranı gösterilmelidir.

Örnek:

```ts
const canAccessUsersPage = hasPermission("users.list");
```

### 7.3 Component / action seviyesi

Kural:

- Sayfa açılmış olsa bile sayfa içindeki tüm bileşenler bağımsız permission kontrolüne tabi olmalıdır.

Örnek:

```ts
const canCreateUser = hasPermission("users.create");
const canReadSensitive = hasPermission("users.read.sensitive");
const canChangeStatus = hasPermission("users.update.status");
const canDeleteUser = hasPermission("users.delete");
```

---

## 8. Backend her zaman tek otorite olmalıdır

Agent, frontend görünürlük kontrollerini güvenlik çözümü olarak ele almamalıdır.

### Zorunlu güvenlik kuralları

- Her endpoint backend tarafında permission kontrolü yapmalıdır.
- Her hassas update isteğinde field-level authorization uygulanmalıdır.
- Kullanıcının izin verilmeyen alanları request payload içinde göndermesi engellenmelidir.
- Backend, yetkisiz isteklerde `403 Forbidden` dönmelidir.

### Doğru endpoint eşleştirme örneği

```txt
GET    /users              -> users.list
GET    /users/:id          -> users.read.basic
POST   /users              -> users.create
PATCH  /users/:id/profile  -> users.update.profile
PATCH  /users/:id/status   -> users.update.status
PATCH  /users/:id/role     -> users.update.role
DELETE /users/:id          -> users.delete
```

### Kaçınılması gereken yaklaşım

```txt
PATCH /users/:id
```

Tek ve genel bir update endpoint'i, permission kontrolünü ve field-level authorization'ı zorlaştırır.

---

## 9. Field-level authorization zorunludur

Agent, update permission'ı olan kullanıcının yalnızca yetkili olduğu alanları değiştirebilmesini sağlamalıdır.

### Örnek politika

```ts
const allowedFieldsByPermission = {
  "users.update.profile": ["firstName", "lastName", "phone"],
  "users.update.status": ["status"],
  "users.update.role": ["roleId"],
};
```

### Zorunlu kural

Request payload içinde kullanıcının sahip olmadığı alanlara ait veri varsa:

- istek reddedilmelidir veya
- yalnızca izinli alanlar işlenmeli ve geri kalanı açıkça engellenmelidir

Varsayılan tercih: **reddetmek**.

---

## 10. Permission dependency nasıl ele alınmalıdır

Bazı permission'lar doğal olarak başka permission'lara ihtiyaç duyabilir.

### Tavsiye edilen yaklaşım

Agent, ilk aşamada örtük dependency sistemi kurmak yerine açık permission ataması kullanmalıdır.

Örnek:

Bir role şu gerekiyorsa:

```txt
users.update.profile
```

çoğu durumda ayrıca şu da eklenmelidir:

```txt
users.read.basic
```

### Gerekçe

- debug daha kolay olur
- permission set'i daha şeffaf olur
- rol yönetimi daha anlaşılır olur

### Kural

Permission dependency uygulanacaksa, bu durum belgelenmeli ve merkezi bir yerde tanımlanmalıdır. Gizli veya dağınık bağımlılıklar oluşturulmamalıdır.

---

## 11. Önerilen minimum permission katmanları

Agent, CRUD ağırlıklı admin panellerde aşağıdaki katmanları baz almalıdır.

### Listeleme

```txt
users.list
orders.list
reports.list
```

### Okuma

```txt
users.read.basic
users.read.detail
users.read.sensitive
```

### Oluşturma

```txt
users.create
orders.create
roles.create
```

### Güncelleme

```txt
users.update.profile
users.update.status
users.update.role
users.update.permissions
```

### Business action

```txt
orders.approve
orders.cancel
payments.refund
users.reset_password
```

### Silme / arşivleme

```txt
users.delete
users.archive
orders.delete
```

### Zorunlu kural

`delete` ile `archive` aynı permission altında birleştirilmemelidir.

---

## 12. Frontend implementation standardı

Agent, frontend tarafta merkezi bir permission helper veya guard sistemi kullanmalıdır.

### Önerilen yardımcı fonksiyonlar

- `hasPermission(permission)`
- `hasAllPermissions([...])`
- `hasAnyPermission([...])`
- `Can` wrapper component
- route guard / page guard

### Zorunlu kural

Permission kontrolleri uygulama içine dağınık `if (role === 'admin')` blokları şeklinde serpiştirilmemelidir.

### Yasak anti-pattern

```ts
if (user.role === "admin") {
  // do something
}
```

Doğru yaklaşım:

```ts
if (hasPermission("users.update.status")) {
  // do something
}
```

---

## 13. Rol tasarımı kuralı

Agent, rolleri permission grubu olarak tasarlamalıdır.

### Örnek

#### Admin

```txt
users.list
users.read.basic
users.read.detail
users.read.sensitive
users.create
users.update.profile
users.update.status
users.update.role
users.delete
```

#### Support

```txt
users.list
users.read.basic
users.update.status
users.reset_password
```

#### Auditor

```txt
users.list
users.read.basic
users.read.detail
```

### Kural

Role, permission set'lerini taşımalıdır; iş kuralı doğrudan role adına gömülmemelidir.

---

## 14. Agent'ın üretmemesi gereken anti-pattern'ler

Agent aşağıdaki yaklaşımları üretmemelidir:

### Anti-pattern 1

Tek bir genel permission ile tüm yetkiyi çözmek:

```txt
users.read
users.update
users.manage
```

### Anti-pattern 2

Yalnızca frontend buton gizlemeyi güvenlik olarak kullanmak

### Anti-pattern 3

Route yetkisini action yetkisi yerine kullanmak

### Anti-pattern 4

Hassas veri alanlarını genel detay ekranına bağlamak

### Anti-pattern 5

CRUD dışı kritik işlemleri `update` içine sıkıştırmak

### Anti-pattern 6

Permission mantığını merkezi helper yerine dağınık component logic içinde çoğaltmak

---

## 15. Agent için uygulanabilir geliştirme talimatı

Agent, projede RBAC veya permission-driven UI ile ilgili bir değişiklik yaparken aşağıdaki sırayı takip etmelidir.

### Adım 1

İlgili resource'u belirle.

Örnek:

- users
- orders
- roles
- reports

### Adım 2

İlgili aksiyonları ayır.

Örnek:

- list
- read.basic
- read.detail
- create
- update.status
- delete
- approve

### Adım 3

Sayfa erişimi ile aksiyon erişimini ayır.

### Adım 4

UI görünürlüğünü navigation, route ve component seviyesinde ayrı ele al.

### Adım 5

Backend tarafında endpoint bazlı authorization ekle.

### Adım 6

Update akışlarında field-level authorization ekle.

### Adım 7

`view yok ama update var` senaryosu varsa full detay ekranı yerine minimum aksiyon arayüzü tasarla.

### Adım 8

Permission isimlerini ve kararlarını kodda ve dokümantasyonda tutarlı şekilde uygula.

---

## 16. Kabul kriterleri

Agent tarafından üretilen çözüm aşağıdaki maddeleri sağlıyorsa doğru kabul edilir:

- Permission isimleri `resource.action.scope` standardına uygundur.
- Route erişimi ile action erişimi birbirinden ayrılmıştır.
- `read` yetkileri gerektiğinde parçalanmıştır.
- `update` yetkileri gerektiğinde parçalanmıştır.
- CRUD dışı iş aksiyonları ayrı permission olarak modellenmiştir.
- Frontend sadece UX kontrolü yapmaktadır.
- Backend nihai authorization kontrolünü yapmaktadır.
- Field-level authorization vardır.
- `view yok ama update var` senaryosu doğru şekilde minimum UI ile çözülmüştür.
- Hassas veri erişimi ayrı permission ile korunmaktadır.

---

## 17. Nihai karar özeti

Agent aşağıdaki prensibi her zaman uygulamalıdır:

> Kullanıcı izinleri sayfa bazlı değil, kaynak + aksiyon + kapsam bazlı ele alınmalıdır. UI görünürlüğü ile iş yetkisi birbirinden ayrılmalı, backend ise her zaman nihai otorite olmalıdır.
