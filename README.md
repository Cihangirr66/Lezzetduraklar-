# Lezzet Durakları Web

Lezzet Durakları Web, kullanıcıların lezzet duraklarını keşfetmesini, mekanları incelemesini ve yönetmesini amaçlayan Django tabanlı bir web uygulamasıdır.

Bu proje, kullanıcı dostu bir arayüz ile restoran, kafe ve farklı lezzet noktalarının listelenmesini hedefler. Web tarafı Django framework kullanılarak geliştirilmiştir.

## Proje Hakkında

Lezzet Durakları Web projesi, kullanıcıların farklı mekanları daha kolay keşfetebilmesi için hazırlanmıştır. Uygulama sayesinde mekanlar listelenebilir, detayları görüntülenebilir ve proje geliştirildikçe yorum, puanlama, kategori ve konum tabanlı özellikler eklenebilir.

Bu proje eğitim, geliştirme ve portfolyo amacıyla hazırlanmıştır.

## Özellikler

* Django tabanlı web uygulaması
* Kullanıcı dostu arayüz
* Mekan listeleme
* Mekan detay sayfası
* Kategori bazlı yapı
* Yönetilebilir proje mimarisi
* Geliştirilmeye açık sistem
* GitHub üzerinden sürüm kontrolü

## Kullanılan Teknolojiler

* Python
* Django
* HTML
* CSS
* JavaScript
* SQLite
* Git & GitHub

## Kurulum

Projeyi bilgisayarınıza indirmek için:

git clone https://github.com/Cihangirr66/Lezzet-Duraklar-.git

Proje klasörüne girin:

cd Lezzet-Duraklar-

Sanal ortam oluşturun:

python -m venv venv

Sanal ortamı aktif edin.

Windows için:

venv\Scripts\activate

MacOS / Linux için:

source venv/bin/activate

Gerekli paketleri yükleyin:

pip install -r requirements.txt

Veritabanı işlemlerini yapın:

python manage.py makemigrations

python manage.py migrate

Projeyi çalıştırın:

python manage.py runserver

Tarayıcıdan açın:

http://127.0.0.1:8000/

## Yerel Ağda Telefonda Açma

Projeyi aynı Wi-Fi ağına bağlı telefonda açmak için bilgisayarın IP adresi ile çalıştırabilirsiniz.

Örnek:

python manage.py runserver 0.0.0.0:8000

Daha sonra telefondan şu şekilde açılır:

http://BILGISAYAR_IP_ADRESI:8000/

Örnek:

http://192.168.1.57:8000/

settings.py içinde ALLOWED_HOSTS alanı uygun şekilde ayarlanmalıdır.

Örnek:

ALLOWED_HOSTS = ["192.168.1.57", "localhost", "127.0.0.1"]

## Proje Yapısı

Lezzet-Duraklar-/
├── manage.py
├── requirements.txt
├── db.sqlite3
├── proje_adi/
├── uygulama_adi/
├── templates/
├── static/
└── README.md

Proje geliştikçe klasör yapısı değişebilir ve yeni modüller eklenebilir.

## Geliştirme Durumu

Bu proje geliştirme aşamasındadır. Zamanla yeni özellikler, tasarım geliştirmeleri ve performans iyileştirmeleri eklenmesi planlanmaktadır.

Planlanan geliştirmeler:

* Mekan arama özelliği
* Konuma göre yakın mekanları listeleme
* Kullanıcı yorumları
* Puanlama sistemi
* Favorilere ekleme
* Yönetim paneli geliştirmeleri
* Mobil uygulama ile bağlantı
* API desteği
* Daha modern arayüz tasarımı

## Mobil Uygulama

Bu projenin Flutter ile geliştirilen mobil tarafı da bulunmaktadır.

Mobil uygulama deposu:

https://github.com/Cihangirr66/Lezzetduraklar--flutter

## Katkıda Bulunma

Projeye katkıda bulunmak isterseniz:

1. Bu repoyu fork edin.
2. Yeni bir branch oluşturun.
3. Geliştirmelerinizi yapın.
4. Pull request gönderin.

Branch oluşturmak için:

git checkout -b yeni-ozellik

## Lisans

Bu proje eğitim ve geliştirme amacıyla hazırlanmıştır.

## Geliştirici

Cihangir Efe Besni

GitHub: https://github.com/Cihangirr66

---

Lezzet Durakları Web projesi, kullanıcıların lezzet duraklarını daha kolay keşfetmesi için Django ile geliştirilmiştir.
