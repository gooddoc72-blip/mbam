import { redirect } from 'next/navigation';
import { HOME_PATH } from './utils/product';

// 카페 전용판에는 대시보드가 없으므로 제품별 첫 화면으로 보낸다.
export default function RootPage() {
    redirect(HOME_PATH);
}
